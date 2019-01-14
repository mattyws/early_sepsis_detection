import json
import os
import re
import time
import pprint
import statistics
from collections import Counter
import sys
import csv

import trabalho_karin.helper as helper
import arff
import pandas as pd

from trabalho_karin import pandas2arff

pp = pprint.PrettyPrinter(indent=5)
date_pattern = "%Y-%m-%d"
datetime_pattern = "%Y-%m-%d %H:%M:%S"
itemid_label = 'ITEMID'
valuenum_label = 'valuenum'
value_label = 'value'
labitems_prefix = 'lab_'
items_prefix = 'item_'
mean_key = 'mean'
std_key = 'std'
csv_file_name = "sepsis_file2.csv"
class_label = "organism_resistence"
interpretation_label = "interpretation"
org_item_label = "ORG_ITEMID"
ab_name_label = 'ANTIBODY'
microbiologyevent_label = "microbiologyevents"
patient_file = 'PATIENTS.csv'
sofa_file = 'sofa.csv'
vasopressor_file = 'vaso_flag.csv'

gender_label = 'GENDER'
ethnicity_label = 'ethnicity'
age_label = 'age'
sofa_label = 'sofa'
birth_label = 'DOB'
vaso_label = 'vasopressor'




def transform_values(row, features_type):
    for key in row:
        itemid = helper.get_itemid_from_key(key)
        if row[key] is not None and features_type[itemid] == helper.MEAN_LABEL:
            mean = 0
            std = 0
            if len(row[key]) > 1:
                mean = sum(row[key]) / len(row[key])
                std = statistics.stdev(row[key])
            elif len(row[key]) != 0:
                mean = row[key][0]
                std = 0
            row[key] = {mean_key: mean } #, std_key: std}
        elif row[key] is not None and features_type[itemid] == helper.CATEGORICAL_LABEL:
                row[key] = Counter(row[key]).most_common(1)[0][0]
    return row


def split_into_columns(row, features_type):
    new_row = dict()
    for key in row:
        itemid = helper.get_itemid_from_key(key)
        if features_type[itemid] == helper.MEAN_LABEL:
            if row[key] is not None:
                for key2 in row[key]:
                    # new_row[key+"_"+key2] = row[key][key2]
                    new_row[key] = row[key][key2]
            else:
                # new_row[key+"_"+mean_key] = None
                new_row[key] = None
                # new_row[key+"_"+std_key] = 0
        else:
            new_row[key] = row[key]
    return new_row


def has_equal(itemid):
    for item in helper.ARE_EQUAL:
        if itemid in item:
            return item[0]
    return itemid


def transform_equal_columns(row, features_type, prefix=""):
    keys_to_remove = []
    for key in row.keys():
        itemid = helper.get_itemid_from_key(key)
        standard_itemid = has_equal(itemid)
        if standard_itemid != itemid:
            if row[key] is not None:
                if row[prefix+standard_itemid] is None:
                    row[prefix + standard_itemid] = row[key]
                else:
                    if features_type[standard_itemid] == helper.MEAN_LABEL or features_type[standard_itemid] == helper.CATEGORICAL_LABEL:
                        row[prefix+standard_itemid].extend(row[key])
                    elif features_type[standard_itemid] == helper.YESNO_LABEL:
                        if row[key] == 1:
                            row[prefix + standard_itemid] = row[key]
            keys_to_remove.append(key)
    for key in keys_to_remove:
        row.pop(key)
    return row

def transform_to_row(filtered_events, features_type, prefix=""):
    row = dict()
    for event in filtered_events:
        itemid = event[itemid_label]
        event_type  = features_type[itemid]
        if prefix+itemid not in row.keys() and event_type == helper.MEAN_LABEL :
            row[prefix+itemid] = []
        elif event_type == helper.CATEGORICAL_LABEL:
            row[prefix+itemid] = []
        elif event_type == helper.YESNO_LABEL:
            row[prefix+itemid] = 0

        if event_type == helper.MEAN_LABEL :
            try:
                if itemid in helper.FARENHEIT_ID:
                    row[prefix + itemid].append(helper.CELCIUS(float(event[valuenum_label])))
                else:
                    row[prefix+itemid].append(float(event[valuenum_label]))
            except:
                row[prefix + itemid].append(0)
        elif event_type == helper.CATEGORICAL_LABEL:
            row[prefix+itemid].append(event[value_label])
        elif event_type == helper.YESNO_LABEL and row[prefix+itemid] == 0:
            row[prefix+itemid] = 1
    for key in features_type.keys():
        if prefix+key not in row:
            row[prefix+key] = None
    row = transform_equal_columns(row, features_type, prefix=prefix)
    row = transform_values(row, features_type)
    row = split_into_columns(row, features_type)
    return row

def transform_all_features_to_row(events, prefix=""):
    row = dict()
    range_re = re.compile('\d-\d')
    for event in events:
        itemid = event[itemid_label]

        if prefix + itemid not in row.keys():
            row[prefix + itemid] = []

        try:
            event_value = float(event[value_label])
        except ValueError:
            if range_re.match(event[value_label]):
                print(event[value_label])
                numbers = re.findall('\d+', event[value_label])
                numbers = [int(n) for n in numbers]
                event_value = sum(numbers) / len(numbers)
            elif event[value_label].startswith('LESS THAN') or event[value_label].startswith('<'):
                numbers = re.findall('\d+', event[value_label])[0]
                if len(numbers) == 0:
                    event_value = 0
                else:
                    event_value = float(numbers[0])
            elif event[value_label].startswith('GREATER THAN') or event[value_label].startswith('>'):
                numbers = re.findall('\d+', event[value_label])[-1]
                if len(numbers) == 0:
                    event_value = 0
                else:
                    event_value = float(numbers[0])
            else:
                event_value = event[value_label]
        row[prefix + itemid].append(event_value)
    for key in row.keys():
        types = set()
        for value in row[key]:
            types.add(type(value))
        types = list(types)
        if len(types) == 1:
            if types[0] == type(int) or types[0] == type(float):
                row[key] = sum(row[key]) / len(row[key])
            else:
                row[key] = Counter(row[key]).most_common(1)[0][0]
        else:
            print(key, row[key])
            for i in range(len(row[key])):
                if type(row[key][i]) == type(str()):
                    if row[key][i].lower() == 'notdone':
                        row[key][i] = 0
                    if range_re.match(event[value_label]):
                        print(event[value_label])
                        numbers = re.findall('\d+', event[value_label])
                        numbers = [int(n) for n in numbers]
                        row[key][i] = sum(numbers) / len(numbers)
            row[key] = sum(row[key]) / len(row[key])
    row = pd.DataFrame(row, index=[0])
    return row

def get_data_from_admitday(json_object, date_str, key="charttime", date=False):
    admittime = time.strptime(date_str, datetime_pattern)
    filtered_objects = []
    for event in json_object:
        event_date = time.strptime(event[key], datetime_pattern)
        if date:
            difference = event_date.tm_mday - admittime.tm_mday
            if difference < 2:
                filtered_objects.append(event)
        else:
            difference = time.mktime(event_date) - time.mktime(admittime)
            if abs(difference) / 86400 <= 1:
                filtered_objects.append(event)
        # break
    return filtered_objects

# print(len(helper.FEATURES_ITEMS_LABELS.keys()) + len(helper.FEATURES_LABITEMS_LABELS.keys()))

def get_antibiotics_classes():
    antibiotics_classes = dict()
    with open('AB_class') as antibiotics_classes_handler:
        antibiotics = []
        ab_class = ''
        for line in antibiotics_classes_handler:
            if len(line.strip()) != 0:
                if line.startswith('\t'):
                    antibiotics.append(line.strip())
                else:
                    if len(antibiotics) != 0:
                        for antibiotic in antibiotics:
                            antibiotics_classes[antibiotic] = ab_class
                    ab_class = line.strip()
                    antibiotics = []
        if len(antibiotics) != 0:
            for antibiotic in antibiotics:
                antibiotics_classes[antibiotic] = ab_class
    return antibiotics_classes

def get_organism_class(events, ab_classes):
    organism_count = dict()
    for event in events:
        if org_item_label in event.keys():
            if event[org_item_label] not in organism_count.keys():
                organism_count[event[org_item_label]] = set()
            if event[interpretation_label] == 'R':
                organism_count[event[org_item_label]].add(ab_classes[event[ab_name_label]])
                if len(organism_count[event[org_item_label]]) == 3:
                    return "R"
    return "S"


def get_patient_age(patient_id, admittime_str):
    admittime = time.strptime(admittime_str, datetime_pattern)
    with open(patient_file, 'r') as patient_file_handler:
        dict_reader = csv.DictReader(patient_file_handler)
        for row in dict_reader:
            if row['subject_id'.upper()] == patient_id:
                dob = time.strptime(row[birth_label], datetime_pattern)
                difference = admittime.tm_year - dob.tm_year - ((admittime.tm_mon, dob.tm_mday) < (admittime.tm_mon, dob.tm_mday))
                return difference
    return None


def get_admission_sofa(hadm_id):
    with open(sofa_file, 'r') as sofa_file_handler:
        dict_reader = csv.DictReader(sofa_file_handler)
        for row in dict_reader:
            if row['hadm_id'] == hadm_id:
                return row['sofa']
    return None


def get_admission_vasopressor(hadm_id):
    with open(vasopressor_file, 'r') as vasopressor_file_handler:
        dict_reader = csv.DictReader(vasopressor_file_handler)
        for row in dict_reader:
            if row['hadm_id'] == hadm_id:
                return row['vaso_flag']
    return None


with open('sepsis_patients4', 'r') as patients_w_sepsis_handler:
    with open(csv_file_name, 'w') as csv_file_handler:
        csv_writer = None
        all_size = 0
        filtered_objects_total_size = 0
        table = pd.DataFrame([])
        not_processes_files = 0
        patients_with_pressure = 0
        total_events_measured = 0
        total_labevents_measured = 0
        labitems_dict = dict()
        chartevents_dict = dict()
        ab_classes = get_antibiotics_classes()
        for line in patients_w_sepsis_handler:
            print(line.strip().split('/')[-1])
            all_size += os.path.getsize(line.strip())
            patient = json.load(open(line.strip(), 'r'))
            patient_age = get_patient_age(patient['subject_id'], patient['admittime'])
            if microbiologyevent_label in patient.keys() and (patient_age > 18 and patient_age < 80):
                filtered_chartevents_object = []
                print("Getting events")
                if 'chartevents' in patient.keys():
                    filtered_chartevents_object = get_data_from_admitday(patient['chartevents'], patient['admittime'],
                                                                         key='charttime', date=False)
                    filtered_objects_total_size += sys.getsizeof(filtered_chartevents_object)

                filtered_labevents_object = []
                if 'labevents' in patient.keys():
                    filtered_labevents_object = get_data_from_admitday(patient['labevents'], patient['admittime'],
                                                                           key='charttime', date=False)
                    filtered_objects_total_size += sys.getsizeof(filtered_labevents_object)

                new_filtered_chartevents = []
                for event in filtered_chartevents_object:
                    if event['ITEMID'] not in chartevents_dict.keys():
                        chartevents_dict[event['ITEMID']] = dict()
                        chartevents_dict[event['ITEMID']]['label'] = event['ITEM']
                        chartevents_dict[event['ITEMID']]['count'] = 0
                    chartevents_dict[event['ITEMID']]['count'] += 1
                    if len(event['error']) != 0 and int(event['error']) == 0:
                        new_filtered_chartevents.append(event)

                total_events_measured += len(new_filtered_chartevents)
                total_labevents_measured += len(filtered_labevents_object)

                for event in filtered_labevents_object:
                    if event['ITEMID'] not in labitems_dict.keys():
                        labitems_dict[event['ITEMID']] = dict()
                        labitems_dict[event['ITEMID']]['label'] = event['ITEM']
                        labitems_dict[event['ITEMID']]['count'] = 0
                    labitems_dict[event['ITEMID']]['count'] += 1

                # new_filtered_chartevents = []
                # for event in filtered_chartevents_object:
                #     if event[itemid_label] in helper.FEATURES_ITEMS_LABELS.keys():
                #         new_filtered_chartevents.append(event)
                #         chartevents_set.add(event['ITEM'])
                #
                # # for event in filtered_chartevents_object:
                # #     try:
                # #         print(event['ITEM'], '--->', type(int(event['value'])), '--->', event['valuenum'])
                # #     except ValueError:
                # #         try:
                # #             print(event['ITEM'], '--->', type(float(event['value'])), '--->', event['valuenum'])
                # #         except ValueError:
                # #             print(event['ITEM'], '--->', type(event['value']), '--->', event['valuenum'])
                #
                # new_filtered_labevents = []
                # for event in filtered_labevents_object:
                #     if event[itemid_label] in helper.FEATURES_LABITEMS_LABELS.keys():
                #         new_filtered_labevents.append(event)
                #         labitems_set.add(event['ITEM'])
                #
                # row_object = transform_to_row(new_filtered_chartevents, helper.FEATURES_ITEMS_TYPE, prefix=items_prefix)
                # row_labevent = transform_to_row(new_filtered_labevents, helper.FEATURES_LABITEMS_TYPE, prefix=labitems_prefix)

                print("Transforming to row")
                row_object = transform_all_features_to_row(new_filtered_chartevents, prefix=items_prefix)
                row_labevent = transform_all_features_to_row(filtered_labevents_object, prefix=labitems_prefix)

                for key in row_labevent.keys():
                    row_object[key] = row_labevent[key]
                row_object[class_label] = get_organism_class(patient[microbiologyevent_label], ab_classes)
                row_object[gender_label] = patient[gender_label]
                row_object[ethnicity_label] = patient[ethnicity_label]
                row_object[age_label.lower()] = patient_age
                row_object[sofa_label] = get_admission_sofa(patient['hadm_id'])
                row_object[vaso_label] = get_admission_vasopressor(patient['hadm_id'])

                # if csv_writer is None:
                #     csv_writer = csv.DictWriter(csv_file_handler, row_object.keys())
                #     csv_writer.writeheader()
                # csv_writer.writerow(row_object)
                # pp.pprint(row_object)
                # exit()
                table = pd.concat([table, row_object], ignore_index=True)
                # table.append(row_object)
            else:
                not_processes_files += 1

        # Getting all fields in file
        # fieldnames = sorted(list(set(k for d in table for k in d)))
        # csv_writer = csv.DictWriter(csv_file_handler, fieldnames, quotechar='\"', quoting=csv.QUOTE_NONNUMERIC)
        # csv_writer.writeheader()
        # for row in table:
        #     csv_writer.writerow(row)
        table.to_csv(csv_file_name, na_rep="?", quoting=csv.QUOTE_NONNUMERIC)
        arff.dump(csv_file_name.replace('.csv', '.arff'), table.values, names=table.columns )
        pandas2arff.pandas2arff(table, csv_file_name.replace('.csv', '_2.arff'))

        print("Number of files that do not had microbiologyevents : {}".format(not_processes_files))
        print("Size of files processed : {} bytes".format(all_size))
        print("Total size of filtered variables : {} bytes".format(filtered_objects_total_size))
        print("Total events measured: {} chartevents, {} labevents".format(total_events_measured, total_labevents_measured))

        with open('labevents_in_dataset.csv', 'w+') as labitems_handler:
            for item in labitems_dict.keys():
                labitems_handler.write('{},{},{}\n'.format(item, labitems_dict[item]['label'].replace(',', ' - '),
                                                           labitems_dict[item]['count']))

        with open('chartevents_in_dataset.csv', 'w+') as chart_handler:
            for item in chartevents_dict.keys():
                chart_handler.write('{},{},{}\n'.format(item, chartevents_dict[item]['label'].replace(',', ' - '),
                                                        chartevents_dict[item]['count']))

