import requests
import json
import sys
import io
import os
import pickle
from bs4 import BeautifulSoup
import pandas as pd


# this is the exclusion list for kdSU's under StudyEventDef with "kdSE"="LogPad"
# e.g.
# <StudyEventDef EventType="None" ID="LogPad.StudyEventDef.337" Name="LogPad" StudyEventRole="None" kdSE="LogPad">
#   <SigningUnitRef ID="LogPad.SigningUnitRef.710" SigningUnitDefID="LogPad.SigningUnitDef.703" kdSU="AnalysisPeriodLabel"/>
#   <SigningUnitRef ID="LogPad.SigningUnitRef.996" SigningUnitDefID="LogPad.SigningUnitDef.976" kdSU="AssigneSense"/>
#   <SigningUnitRef ID="LogPad.SigningUnitRef.459" SigningUnitDefID="LogPad.SigningUnitDef.257" kdSU="Assignment"/>
#   <SigningUnitRef ID="LogPad.SigningUnitRef.640" SigningUnitDefID="LogPad.SigningUnitDef.633" kdSU="APC"/>
#   ...

kdSU_exclusion_list = ["AnalysisPeriodLabel", "AssigneSense", "Assignment", "APC", "EndWebProUse", "EndLogPadUse", "ICAC", "ISAC", "NewCaregiver", "RegisterASMA1", "AddUser", "DeactivateUser", "Replacement", "Synchronization", "Training", "VisitEnd", "VisitStart", "Activation", "EstablishID", "ConfirmID"]
su_exclusion_list = ["EndWebProUse"]
# this is the list of kdIG names that are ignored
# e.g.
# <SigningUnitDef ID="LogPad.SigningUnitDef.1875" kdSU="HHTrainingModule" Name="Handheld Training Module">
#   <ItemGroupRef ID="LogPad.ItemGroupRef.1876" ItemGroupStyle="SingleColumnInTable" HeaderType="None" ItemGroupDefID="LogPad.ItemGroupDef.942" kdIG="Protocol" Name="Protocol"/>
#   <ItemGroupRef ID="LogPad.ItemGroupRef.1877" ItemGroupStyle="SingleColumn" HeaderType="None" ItemGroupDefID="LogPad.ItemGroupDef.236" kdIG="Header" Name="Header"/>
#   <ItemGroupRef ID="LogPad.ItemGroupRef.1878" ItemGroupStyle="SingleColumnInTable" HeaderType="None" ItemGroupDefID="LogPad.ItemGroupDef.365" kdIG="FormLevelData" Name="Form Level Data"/>
#   <ItemGroupRef ID="LogPad.ItemGroupRef.1880" ItemGroupStyle="SingleColumnInTable" HeaderType="None" ItemGroupDefID="LogPad.ItemGroupDef.906" kdIG="CG" Name="Caregiver Submit"/>
#   ...

kdIG_exclusion_list = ["Protocol", "Header", "FormLevelData", "CG", "LogPadPerformance", "EntryMode", "NetProInformation", "TimeZone", "Phase"]

# for study designer if ig is equal to any item in the list below, it is ignored.
ig_exclusion_list = ["-", ""]

# this is used for writing buffer out to terminal.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="UTF-8")

# ---------------------------------------- initialization


def user_input_pn_metadata_file_name():
    """
    have user input the name of the pn metadata file they wish to parse.
    """
    is_name_in_directory = False
    while not is_name_in_directory:
        pn_metadata_file_name = input("Enter the full name of the pn metadata xml file you would like to parse (e.g. pn_metadata.xml): ")
        if not os.path.exists("{}".format(pn_metadata_file_name)):
            print("File not found. Make sure the file name is *.xml and it resides in the same path as main.py ...")
        else:
            is_name_in_directory = True

    return pn_metadata_file_name


def find_study_protocols(pn_metadata_file_name):
    """
    parses pn metadata file and returns a list of study protocols
    """
    with open(pn_metadata_file_name, 'r') as f:

        soup = BeautifulSoup(f.read(), 'lxml')
        study_name = soup.body.study.metadata.identification.description.string
        soup_datadictionary = soup.body.study.metadata.datadictionary

        pn_metadata_protocol = []
        for codelistdef in soup_datadictionary.find_all('codelistdef'):
            if codelistdef['name'] == 'Protocol':
                for codelistitem in codelistdef.find_all('codelistitem'):
                    protocol = codelistitem["description"]
                    if protocol not in ['<Unspecified Protocol>']:
                        pn_metadata_protocol.append(protocol)

    # soup_datadictionary will be used later to find kdSUs.
    return soup_datadictionary, pn_metadata_protocol

# ---------------------------------------- parsing pn_metadata


def find_pn_metadata_kdSU_values(soup_datadictionary, kdSU_exclusion_list):
    """
    find the list of nontrivial kdSU values in pn_metadata
    """
    all_kdSU_values = []

    for studyeventdef in soup_datadictionary.find_all('studyeventdef'):
        if studyeventdef['kdse'] == 'LogPad':
            for signingunitref in studyeventdef.find_all('signingunitref'):
                all_kdSU_values.append(signingunitref['kdsu'])

    valid_kdSU_values = list(set(all_kdSU_values) - set(kdSU_exclusion_list))

    return valid_kdSU_values


def create_pn_metadata_kdSU_name_dictionary(valid_kdSU_values, soup_datadictionary):
    """
    returns a dictionary that maps kdsu to corresponding name
    """
    kdSU_Name_map = {}

    for signingunitdef in soup_datadictionary.find_all('signingunitdef'):
        if signingunitdef['kdsu'] in valid_kdSU_values:
            kdSU_Name_map[signingunitdef['kdsu']] = signingunitdef['name']

    return kdSU_Name_map


def create_pn_metadata_kdSU_kdIG_dictionary(valid_kdSU_values, soup_datadictionary, kdIG_exclusion_list):
    """
    finds the list of nontrivial kdIG values in pn_metadata
    """

    kdSU_kdIG_map = {}

    for signingunitdef in soup_datadictionary.find_all('signingunitdef'):
        if signingunitdef['kdsu'] in valid_kdSU_values:
            kdSU_kdIG_map[signingunitdef['kdsu']] = []
            for itemgroupref in signingunitdef.find_all('itemgroupref'):
                kdSU_kdIG_map[signingunitdef['kdsu']].append(itemgroupref['kdig'])

    # removing items from kdIG exclusion list:
    for kdSU, kdIG_list in kdSU_kdIG_map.items():
        valid_kdIG_list = list(set(kdIG_list) - set(kdIG_exclusion_list))
        kdSU_kdIG_map[kdSU] = valid_kdIG_list

    return kdSU_kdIG_map


def create_pn_metadata_kdIG_kdIT_dictionary(kdSU_kdIG_map, soup_datadictionary):
    """
    finds the list of nontrivial kdIG values in pn_metadata
    """

    kdIG_kdIT_map = {}

    for itemgroupdef in soup_datadictionary.find_all('itemgroupdef'):
        kdIG_kdIT_map[itemgroupdef['kdig']] = []
        for itemref in itemgroupdef.find_all('itemref'):
            kdIG_kdIT_map[itemgroupdef['kdig']].append(itemref['kdit'])

    return kdIG_kdIT_map


def create_pn_metadata_kdSU_kdIG_kdIT_dictionary(soup_datadictionary, kdSU_exclusion_list, kdIG_exclusion_list):
    """
    creates a nested dictionary that holds kdSU kdIG kdIT relationships.
    """
    valid_kdSU_values = find_pn_metadata_kdSU_values(soup_datadictionary, kdSU_exclusion_list)
    print("pn_metadata list of valid kdSU values: \n{} \n".format(valid_kdSU_values))
    kdSU_kdIG_map = create_pn_metadata_kdSU_kdIG_dictionary(valid_kdSU_values, soup_datadictionary, kdIG_exclusion_list)
    kdIG_kdIT_map = create_pn_metadata_kdIG_kdIT_dictionary(kdSU_kdIG_map, soup_datadictionary)

    # kdsu => name map:
    kdSU_Name_map = create_pn_metadata_kdSU_name_dictionary(valid_kdSU_values, soup_datadictionary)

    kdSU_kdIG_kdIT_map = {}  # initializing
    for kdSU, kdIG_list in kdSU_kdIG_map.items():
        kdSU_kdIG_kdIT_map[kdSU] = {}
        for kdIG in kdIG_list:
            kdSU_kdIG_kdIT_map[kdSU][kdIG] = kdIG_kdIT_map[kdIG]

    return kdSU_Name_map, kdSU_kdIG_kdIT_map

# ---------------------------------------- getting study designer json


def get_all_study_design_ids(pn_metadata_protocol):
    """
    get all studies in json format and serialize if not done alraedy
    """

    response = requests.get("http://naphznv3a.phtstudy.com:3006/api/v2/designs")
    content = response.content.decode('latin-1').encode('utf8')
    study_dict_list = json.loads(content)

    study_design_ids = []

    for study in study_dict_list:
        if study['protocol'] == pn_metadata_protocol:
            study_design_ids.append(study['designId'])

    return study_design_ids


def find_latest_design_id(study_design_ids):
    """
    returns the latest study designId
    """
    study_design_ids_splitted = [item.split('@') for item in study_design_ids]
    for index, item in enumerate(study_design_ids_splitted):
        if len(item) == 1:
            study_design_ids_splitted[index] = [item[0], '-1']

    sorted_study_design_ids_splitted = sorted(study_design_ids_splitted, key=lambda item: float(item[1]))
    latest_design_id = '@'.join(sorted_study_design_ids_splitted[-1])

    return latest_design_id


def get_study_designer_json(soup_datadictionary, pn_metadata_protocol):
    """
    use the latest design id to retrieve the correct study designer json
    """
    study_design_ids = get_all_study_design_ids(pn_metadata_protocol)
    if len(study_design_ids) == 0:
        print("Unable to find design ids associated with the protocol name in pn_metadata xml file. You may enter your design idea of interest here: ")
        latest_design_id = input("Enter the full name of the pn metadata xml file you would like to parse (e.g. pn_metadata.xml): ")

    else:
        print("the list of all study design ids based on study protocol extracted from pn_metadata: \n{} \n".format(study_design_ids))
        latest_design_id = find_latest_design_id(study_design_ids)
        print("the latest study design id: \n{} \n".format(latest_design_id))

    response = requests.get("http://naphznv3a.phtstudy.com:3010/api/v1/json/export/{0}/ods".format(latest_design_id))
    content = response.content.decode('latin-1').encode('utf8')
    study_designer_json = json.loads(content)
    print("retrieved study json from http request to: \nhttp://naphznv3a.phtstudy.com:3010/api/v1/json/export/{0}/ods \n".format(latest_design_id))

    return study_designer_json

# ---------------------------------------- parsing study designer


def create_study_designer_su_name_dictionary(study_designer_json, su_exclusion_list):
    """
    creates a dictionary that maps su => name
    """
    try:
        su_name_map = {}
        for questionnaire in study_designer_json['questionnaires']:
            if questionnaire['su'] not in su_exclusion_list:
                su_name_map[questionnaire['su']] = questionnaire['name']

        return su_name_map

    except KeyError as e:
        print("study designer API get request returned an incorrect json\n:{}".format(study_designer_json))
        sys.exit()


def create_study_designer_su_ig_it_dictionary(study_designer_json, su_exclusion_list, ig_exclusion_list):
    """
    creates a nested dictionary for su ig it relationships
    """

    su_name_map = create_study_designer_su_name_dictionary(study_designer_json, su_exclusion_list)
    su_ig_it_map = {}

    for questionnaire in study_designer_json['questionnaires']:
        if questionnaire['su'] not in su_exclusion_list:
            su_ig_it_map[questionnaire['su']] = {}
            questionnaire_unique_ig_list = []
            for item in questionnaire['items']:
                if item['ig'] not in ig_exclusion_list:
                    if item['ig'] not in questionnaire_unique_ig_list:
                        su_ig_it_map[questionnaire['su']][item['ig']] = []
                        su_ig_it_map[questionnaire['su']][item['ig']].append('.'.join([item['it'], str(item['includeInReports'])]))
                        questionnaire_unique_ig_list.append(item['ig'])
                    else:
                        su_ig_it_map[questionnaire['su']][item['ig']].append('.'.join([item['it'], str(item['includeInReports'])]))

    return su_name_map, su_ig_it_map


# ---------------------------------------- creating csvs and report diffs
def smaller_list_to_larger_comparison(sm, lg):
    """
    this function and next are used to insert --- MISMATCH --- in report columns where values mismatch.
    make sure both lists are sorted before calling these functions.
    """
    for i in range(len(sm)):
        if sm[i] != lg[i]:
            if sm[i] > lg[i]:
                sm.insert(i, '~~~ MISMATCH ~~~')
            else:
                lg.insert(i, '~~~ MISMATCH ~~~')


def larger_list_to_smaller_comparison(list_a, list_b):

    lg = list_a
    sm = list_b

    if len(list_b) > len(list_a):
        lg = list_b
        sm = list_a

    for i in range(len(lg)):
        if i < len(sm):
            if lg[i] != sm[i] and sm[i] != '~~~ MISMATCH ~~~' and lg[i] != '~~~ MISMATCH ~~~':
                if sm[i] > lg[i]:
                    sm.insert(i, '~~~ MISMATCH ~~~')
                else:
                    lg.insert(i, '~~~ MISMATCH ~~~')
                    larger_list_to_smaller_comparison(lg, sm)
        else:
            sm.append('~~~ MISMATCH ~~~')


def add_includeInReports(ig_it_column, dict_includeInReports):
    """
    this function is meant to introduce ~~~ MISMATCH ~~~ values in the correct places in the it.IncludeInReports column.
    """
    it_includeInReports = []
    for item in ig_it_column:
        if item != "~~~ MISMATCH ~~~":
            it = item.split('-->')[1]
            it_includeInReports.append("{}-->{}".format(it, dict_includeInReports[it]))
        else:
            it_includeInReports.append("~~~ MISMATCH ~~~")

    return it_includeInReports


# ----------------------------------------


def create_kdsu_su_name_csv_diff_report(kdSU_name_map, su_name_map):

    df_dict = {}
    df_dict['kdsu_name'] = []
    df_dict['su_name'] = []
    for kdsu, name in kdSU_name_map.items():
        df_dict['kdsu_name'].append(name)
    for su, name in su_name_map.items():
        df_dict['su_name'].append(name)

    # report
    kdsu_su_diff_name = sorted(list(set(df_dict['kdsu_name']) - set(df_dict['su_name'])))
    su_kdsu_diff_name = sorted(list(set(df_dict['su_name']) - set(df_dict['kdsu_name'])))

    print("------------------------------- kdsu - su - names -------------------------------")
    print("pn_metadata has the following kdsu names that are not present in study designer su name set: (kdsu_name vs. su_name)")
    if len(kdsu_su_diff_name) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(kdsu_su_diff_name):
            print('.    '.join([str(count + 1), item]))
    print("study_designer has the following su names values that are not present in pn_metadata kdsu name set: (su name vs. kdsu name)")
    if len(su_kdsu_diff_name) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(su_kdsu_diff_name):
            print('.    '.join([str(count + 1), item]))
    print("\n")
    # in case of rows not matching count, append the smaller one with 'ZZZ-None' so these rows end up at the buttom when column is sorted.
    column_length_difference = len(df_dict['kdsu_name']) - len(df_dict['su_name'])

    for column_name, column_rows in df_dict.items():
        df_dict[column_name] = sorted(column_rows)

    if column_length_difference > 0:
        smaller_list_to_larger_comparison(df_dict['su_name'], df_dict['kdsu_name'])
        larger_list_to_smaller_comparison(df_dict['kdsu_name'], df_dict['su_name'])

    elif column_length_difference < 0:
        smaller_list_to_larger_comparison(df_dict['kdsu_name'], df_dict['su_name'])
        larger_list_to_smaller_comparison(df_dict['su_name'], df_dict['kdsu_name'])

    df = pd.DataFrame(data=df_dict)
    df.to_csv("csvs/{}_csvs/kdsu_su_name.csv".format(pn_metadata_file_name))
    return df


def create_kdsu_su_id_csv_diff_report(kdSU_name_map, su_name_map):

    df_dict = {}
    df_dict['kdsu'] = []
    df_dict['su'] = []
    for kdsu, name in kdSU_name_map.items():
        df_dict['kdsu'].append(kdsu)
    for su, name in su_name_map.items():
        df_dict['su'].append(su)

    # report
    kdsu_su_diff_id = sorted(list(set(df_dict['kdsu']) - set(df_dict['su'])))
    su_kdsu_diff_id = sorted(list(set(df_dict['su']) - set(df_dict['kdsu'])))

    print("------------------------------- kdsu - su - id -------------------------------")
    print("pn_metadata has the following kdsu id values that are not present in study designer su id set: (kdsu vs. su)")
    if len(kdsu_su_diff_id) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(kdsu_su_diff_id):
            print('.    '.join([str(count + 1), item]))
    print("study_designer has the following su id values that are not present in pn_metadata kdsu id set: (su vs. kdsu)")
    if len(su_kdsu_diff_id) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(su_kdsu_diff_id):
            print('.    '.join([str(count + 1), item]))
    print("\n")

    # in case of rows not matching count, append the smaller one with 'ZZZ-None' so these rows end up at the buttom when column is sorted.
    column_length_difference = len(df_dict['kdsu']) - len(df_dict['su'])

    for column_name, column_rows in df_dict.items():
        df_dict[column_name] = sorted(column_rows)

    if column_length_difference > 0:
        smaller_list_to_larger_comparison(df_dict['su'], df_dict['kdsu'])
        larger_list_to_smaller_comparison(df_dict['kdsu'], df_dict['su'])

    elif column_length_difference < 0:
        smaller_list_to_larger_comparison(df_dict['kdsu'], df_dict['su'])
        larger_list_to_smaller_comparison(df_dict['su'], df_dict['kdsu'])

    df = pd.DataFrame(data=df_dict)
    df.to_csv("csvs/{}_csvs/kdsu_su_id.csv".format(pn_metadata_file_name))
    return df


def create_kdig_ig_id_csv_diff_report(kdSU_kdIG_kdIT_map, su_ig_it_map):

    df_dict = {}
    df_dict['kdsu-->kdig'] = []
    df_dict['su-->ig'] = []
    for kdsu, kdig_dict in kdSU_kdIG_kdIT_map.items():
        for kdig, kdit_list in kdig_dict.items():
            df_dict['kdsu-->kdig'].append('-->'.join([kdsu, kdig]))

    for su, ig_dict in su_ig_it_map.items():
        for ig, it_list in ig_dict.items():
            df_dict['su-->ig'].append('-->'.join([su, ig]))

    # report
    kdig_ig_diff = sorted(list(set(df_dict['kdsu-->kdig']) - set(df_dict['su-->ig'])))
    ig_kdig_diff = sorted(list(set(df_dict['su-->ig']) - set(df_dict['kdsu-->kdig'])))

    print("------------------------------- kdig - ig - id -------------------------------")
    print("pn_metadata has the following kdig values that are not present in study designer ig set: (kdsu-->kdig vs. su-->ig)")
    if len(kdig_ig_diff) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(kdig_ig_diff):
            print('.    '.join([str(count + 1), item]))
    print("study_designer has the following su values that are not present in pn_metadata kdsu set: (su-->ig vs. kdsu-->kdig)")
    if len(ig_kdig_diff) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(ig_kdig_diff):
            print('.    '.join([str(count + 1), item]))
    print("\n")

    column_length_difference = len(df_dict['kdsu-->kdig']) - len(df_dict['su-->ig'])

    for column_name, column_rows in df_dict.items():
        df_dict[column_name] = sorted(column_rows)

    if column_length_difference > 0:
        smaller_list_to_larger_comparison(df_dict['su-->ig'], df_dict['kdsu-->kdig'])
        larger_list_to_smaller_comparison(df_dict['kdsu-->kdig'], df_dict['su-->ig'])

    elif column_length_difference < 0:
        smaller_list_to_larger_comparison(df_dict['kdsu-->kdig'], df_dict['su-->ig'])
        larger_list_to_smaller_comparison(df_dict['su-->ig'], df_dict['kdsu-->kdig'])

    df = pd.DataFrame(data=df_dict)
    df.to_csv("csvs/{}_csvs/kdsu.kdig_su.ig_id.csv".format(pn_metadata_file_name))
    return df


def create_kdit_it_id_csv_diff_report(kdSU_kdIG_kdIT_map, su_ig_it_map):
    '''
    this function outputs two dataframes; one with columns kdig-->kdit ig-->it.
    '''

    df_dict = {}

    df_dict['kdig-->kdit'] = []
    df_dict['ig-->it'] = []

    df_dict_includeInReports = {}

    for kdsu, kdig_dict in kdSU_kdIG_kdIT_map.items():
        for kdig, kdit_list in kdig_dict.items():
            for kdit in kdit_list:
                df_dict['kdig-->kdit'].append('-->'.join([kdig, kdit]))

    for su, ig_dict in su_ig_it_map.items():
        for ig, it_list in ig_dict.items():
            for it in it_list:
                temp = it.split('.')
                it_without_includeinreport = temp[0]
                df_dict['ig-->it'].append('-->'.join([ig, it_without_includeinreport]))
                df_dict_includeInReports[it_without_includeinreport] = temp[1]

    # report
    kdit_it_diff = sorted(list(set(df_dict['kdig-->kdit']) - set(df_dict['ig-->it'])))
    it_kdit_diff = sorted(list(set(df_dict['ig-->it']) - set(df_dict['kdig-->kdit'])))

    print("------------------------------- kdit - it - id -------------------------------")
    print("pn_metadata has the following kdit values that are not present in study designer it set: (kdig-->kdit vs. ig-->it)")
    if len(kdit_it_diff) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(kdit_it_diff):
            print('.    '.join([str(count + 1), item]))
    print("study_designer has the following it values that are not present in pn_metadata kdit set: (ig-->it vs. kdig-->kdit)")
    if len(it_kdit_diff) == 0:
        print("ALL VALUES MATCH")
    else:
        for count, item in enumerate(it_kdit_diff):
            print('.    '.join([str(count + 1), item]))
    print("\n")

    column_length_difference = len(df_dict['kdig-->kdit']) - len(df_dict['ig-->it'])

    for column_name, column_rows in df_dict.items():
        df_dict[column_name] = sorted(column_rows)

    if column_length_difference > 0:
        smaller_list_to_larger_comparison(df_dict['ig-->it'], df_dict['kdig-->kdit'])
        larger_list_to_smaller_comparison(df_dict['kdig-->kdit'], df_dict['ig-->it'])
        df_dict['it-->IncludeInReports'] = add_includeInReports(df_dict['ig-->it'], df_dict_includeInReports)

    elif column_length_difference < 0:
        smaller_list_to_larger_comparison(df_dict['kdig-->kdit'], df_dict['ig-->it'])
        larger_list_to_smaller_comparison(df_dict['ig-->it'], df_dict['kdig-->kdit'])
        df_dict['it-->IncludeInReports'] = add_includeInReports(df_dict['ig-->it'], df_dict_includeInReports)

    df = pd.DataFrame(data=df_dict)
    df.to_csv("csvs/{}_csvs/kdig.kdit_ig.it_it.includeInReports_id.csv".format(pn_metadata_file_name))
    return df


if __name__ == "__main__":
    pn_metadata_file_name = user_input_pn_metadata_file_name()
    # pn_metadata_file_name = "pn_metadata.xml"
    print("parsing {}... \n".format(pn_metadata_file_name))

    soup_datadictionary, pn_metadata_protocol = find_study_protocols(pn_metadata_file_name)
    print("the protocols for this study according to {0} are: \n{1} \n".format(pn_metadata_file_name, pn_metadata_protocol))

    # pn_metadata
    kdSU_name_map, kdSU_kdIG_kdIT_map = create_pn_metadata_kdSU_kdIG_kdIT_dictionary(soup_datadictionary, kdSU_exclusion_list, kdIG_exclusion_list)
    # print("pn_metadata kdsu => name: \n{} \n".format(kdSU_name_map))
    # print("pn_metadata kdSU => kdIG => kdIT: \n{} \n".format(kdSU_kdIG_kdIT_map))

    # getting study designer study json
    study_designer_json = get_study_designer_json(soup_datadictionary, pn_metadata_protocol)

    # study designer
    # print("parsing study designer json ... \n")
    su_name_map, su_ig_it_map = create_study_designer_su_ig_it_dictionary(study_designer_json, su_exclusion_list, ig_exclusion_list)
    # print("study_designer su => name: \n{} \n".format(su_name_map))
    # print("study_designer su => ig => it: \n{} \n".format(su_ig_it_map))

    # print(su_ig_it_map)

    # ---------------------------------------- creating csvs + reports
    if not os.path.exists("csvs/{}_csvs".format(pn_metadata_file_name)):
        os.makedirs("csvs/{}_csvs".format(pn_metadata_file_name))

    report_file_name = "{}_report.txt".format(pn_metadata_file_name)

    if not os.path.isdir("reports"):
        os.mkdir("reports")

    if os.path.exists("reports/{}".format(report_file_name)):
        os.remove("reports/{}".format(report_file_name))

    with open("reports/{}".format(report_file_name), "a+") as file:

        dataframe = create_kdsu_su_name_csv_diff_report(kdSU_name_map, su_name_map)
        file.write(dataframe.to_string())
        file.write('\n\n')

        dataframe = create_kdsu_su_id_csv_diff_report(kdSU_name_map, su_name_map)
        file.write(dataframe.to_string())
        file.write('\n\n')

        dataframe = create_kdig_ig_id_csv_diff_report(kdSU_kdIG_kdIT_map, su_ig_it_map)
        file.write(dataframe.to_string())
        file.write('\n\n')

        dataframe = create_kdit_it_id_csv_diff_report(kdSU_kdIG_kdIT_map, su_ig_it_map)
        file.write(dataframe.to_string())
        file.write('\n\n')
