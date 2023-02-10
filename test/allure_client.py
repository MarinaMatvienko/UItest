"""
Модуль для загрузки данных в Allure
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import traceback

import allure
import requests
from kafka.consumer.fetcher import ConsumerRecord
from sqlalchemy.inspection import inspect

import config
from helpers.vault import Vault


def _json_serializator(value):
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')
    elif inspect(value, False):
        return value.dict()
    return str(value)


def allure_attach(obj, name, is_json=True, is_xml=False):
    """
    Функция для прикрепления данных к тестам
    """
    if isinstance(obj, ConsumerRecord):
        attach_data = f'Key: {obj.key.decode()}\n' \
                      f'Value: \n{json.dumps(obj.value, indent=2, ensure_ascii=False, default=_json_serializator)}'
    elif isinstance(obj, requests.Response):
        attach_data = f'Request URL: {obj.request.url}\n' \
                      f'Request method: {obj.request.method}\n' \
                      f'Request body: {obj.request.body}\n' \
                      f'Response status code: {obj.status_code}\n' \
                      f'Response text: {obj.text}'
    elif is_json:
        attach_data = json.dumps(obj, indent=2, ensure_ascii=False, default=_json_serializator)
    elif is_xml:
        attach_data = obj
    else:
        attach_data = str(obj)
    # для локальных запусков:
    if not os.environ.get('CI_PROJECT_NAME'):
        print(f'\n{name}:\n{attach_data}')
    allure.attach(attach_data, name=name, attachment_type=allure.attachment_type.JSON)


def _get_results_path():
    """
    Возвращает полный путь к папке с результатами
    """
    return os.path.join(os.path.dirname(os.path.abspath(config.__file__)), config.allure_results)


def _check_report_files():
    """
    Проверяет наличие файлов с результатами
    """
    results_path = _get_results_path()
    for filename in os.listdir(results_path):
        if filename.endswith('result.json'):
            return True
    else:
        return False


def clean_results():
    """
    Очищает папку с результатами
    """
    results_path = _get_results_path()
    for filename in os.listdir(results_path):
        file_path = os.path.join(results_path, filename)
        try:
            if filename.startswith('.'):
                continue
            elif os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')


def _check_output(cmd):
    """
    Обертка над subprocess.check_output
    """
    print('run: "%s"' % ' '.join(cmd))
    out = subprocess.check_output(cmd, timeout=60)
    print(out)
    return out


def upload_results():
    """
    Загруска результатов в Allure TestOps
    """
    if not _check_report_files():
        return None
    vault = Vault()
    os.environ['ALLURE_TOKEN'] = vault.get_secret('allure_token')
    try:
        if os.environ.get('CI_PROJECT_NAME') and os.environ.get('CI_PIPELINE_ID'):
            launch_name = f'{os.environ.get("CI_PROJECT_NAME")} #{os.environ.get("CI_PIPELINE_ID")}'
        else:
            launch_name = f'Local launch {datetime.datetime.now().isoformat()}'
        out = _check_output([
            'allurectl', 'launch', 'create', '--launch-name', launch_name,
            '-p', config.allure_project_id, '-e', config.allure_endpoint, '-o', 'json'
        ])
        launch_id = re.search('"id": [0-9]+', out.decode()).group(0)[6:]
        _check_output([
            'allurectl', 'upload', config.allure_results, '--launch-id', launch_id,
            '--project-id', config.allure_project_id, '-e', config.allure_endpoint
        ])
        allure_report_url = f'{config.allure_endpoint}launch/{launch_id}/tree?treeId={config.allure_tree_id}'
    except Exception:
        print(f'Failed allurectl upload: {traceback.format_exc()}')
        allure_report_url = None
    print('allure_report_url:', allure_report_url)
    return allure_report_url


def _rename(allure_dir):
    """
    Обработка отчетов для старого Allure
    """
    print('RENAME')
    files = os.listdir(allure_dir.strip())
    file_report = False
    for file in files:
        file_result = re.findall(r'.{0,}-testsuite.xml', file)
        if len(file_result) > 0:
            file_report = file
    print('file_report')
    print(file_report)
    if file_report:
        fileName = '{}/{}'.format(allure_dir, file_report)
        newfileName = '{}/names.xml'.format(allure_dir)
        with open(fileName, 'r') as f1, open(newfileName, 'w') as f2:
            lines = f1.readlines()
            for line in lines:
                result = re.findall(r'^<name>[.]{1,}\w{0,}.{0,}</name>$', line.strip())
                if len(result) > 0:
                    split_line = line.split('.', 7)
                    new_name = '<name>' + split_line[len(split_line) - 1].replace('</name>\n', '') + '</name>'
                    new_line = re.sub(r'<name>[.]{1,}\w{0,}.{0,}</name>', new_name, line)
                    f2.write(new_line)
                else:
                    f2.write(line)
        with open(newfileName, 'r') as f:
            old_data = f.read()
        with open(fileName, 'w') as f:
            f.write(old_data)


def upload_results_old():
    """
    Загруска результатов в Allure
    """
    if not _check_report_files():
        return None
    results_path = _get_results_path()
    try:
        _rename(results_path)
        current_dir = os.getcwd()
        shutil.make_archive('allure_results', 'zip', results_path)
        zip_file = os.path.join(results_path, 'allure_results.zip')
        shutil.move(os.path.join(current_dir, 'allure_results.zip'), zip_file)
        files = {'file': open(zip_file, 'rb')}
        url = f'{config.old_allure_endpoint}upload'
        if os.environ.get('CI_COMMIT_REF_NAME'):
            version = os.environ.get('CI_COMMIT_REF_NAME')
        else:
            version = 'local'
        params = {
            'group': config.old_allure_group,
            'project': config.old_allure_project,
            'version': version
        }
        response = requests.post(url, files=files, params=params)
        allure_report_url = response.text.strip()
        re_pattern = f'^{config.old_allure_endpoint}+'
        assert re.match(re_pattern, allure_report_url)
    except Exception:
        print(f'Failed old allurectl upload: {traceback.format_exc()}')
        allure_report_url = None
    print('allure_report_url:', allure_report_url)
    return allure_report_url
