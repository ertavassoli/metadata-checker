import requests
import json
import sys
import io
from os import path
import pickle
from bs4 import BeautifulSoup


def latest_design_id_finder(study_design_ids):
    study_design_ids_splitted = [item.split('@') for item in study_design_ids]
    for index, item in enumerate(study_design_ids_splitted):
        if len(item) == 1:
            study_design_ids_splitted[index] = [item[0], '-1']

    sorted_study_design_ids_splitted = sorted(study_design_ids_splitted, key=lambda item: float(item[1]))
    latest_design_id = '@'.join(sorted_study_design_ids_splitted[-1])
    return latest_design_id


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="UTF-8")

# retrieving study protocols
with open('pn_metadata.xml', 'r') as f:

    soup = BeautifulSoup(f.read(), 'lxml')
    study_name = soup.body.study.metadata.identification.description.string
    soup_datadictionary = soup.body.study.metadata.datadictionary

    pn_metadata_protocol = []
    for codelistdef in soup_datadictionary.find_all('codelistdef'):
        if codelistdef['name'] == 'Protocol':
            for codelistitem in codelistdef.find_all('codelistitem'):
                pn_metadata_protocol.append(codelistitem["description"])

# retrieving design id
if not path.exists("study_dict_list.pickle"):

    response = requests.get("http://naphznv3a.phtstudy.com:3006/api/v2/designs")
    content = response.content.decode('latin-1').encode('utf8')
    study_dict_list = json.loads(content)
    with open("study_dict_list.pickle", "wb") as file:
        pickle.dump(study_dict_list, file)
else:
    with open("study_dict_list.pickle", "rb") as file:
        study_dict_list = pickle.load(file)

study_design_ids = []

for study in study_dict_list:
    if study['protocol'] == pn_metadata_protocol:
        study_design_ids.append(study['designId'])

latest_design_id = latest_design_id_finder(study_design_ids)

print(latest_design_id)

response = requests.get("http://naphznv3a.phtstudy.com:3010/api/v1/json/export/{0}/ods".format(latest_design_id))
content = response.content.decode('latin-1').encode('utf8')
study_designer_json = json.loads(content)

print(study_designer_json)
