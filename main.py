import requests
import json
import sys
import io
from os import path
import pickle
from bs4 import BeautifulSoup

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

for study in study_dict_list:
    if study['protocol'] == pn_metadata_protocol:
        print(study['designId'])


# print(studies_dict)
# print(response.json())

# response = requests.get("http://naphznv3a.phtstudy.com:3010/api/v1/json/export/{0}/ods".format(default_id))

# default_id = ''
# response = requests.get("http://naphznv3a.phtstudy.com:3010/api/v1/json/export/5b0fea03976a8f1989b789a3/ods")
# content = response.content.decode('cp1252').encode('utf8')
# json_dict = json.loads(content)
# print(type(json_dict))

# for codelistdef in soup.findAll('CodelistDef'):
