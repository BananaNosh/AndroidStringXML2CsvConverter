import argparse
import os
import re

import xmltodict

VALUE_FOLDER = "values"
STRING_FILENAME = "strings.xml"
STRING_VALUE_PATTERN = r"<string [^>]*name=\"(\w+)\"[^>]*>"
COMMENT_PATTERN = r" {4}<!--(.*)-->"
COMMENT_XML = r'    <string comment="\1"/>'
NAME_KEY = "@name"
TEXT_KEY = "#text"
TRANSLATABLE_KEY = "@translatable"
EXTRA_SEP_INTRA = "="
EXTRA_SEP_INTER = ";"
NOT_TRANSLATABLE_TEXT = "not-translatable"
COMMENT_CSV_PATTERN = r"%%([^%]+)%%"


class NoDefaultStringFile(FileNotFoundError):
    pass


def read_arguments():
    parser = argparse.ArgumentParser(description="Convert string xml to csv")
    parser.add_argument("res_folder", help="The resource folder containing the string.xml files/folders")
    parser.add_argument("csv_file", help="The (destination) csv file")
    parser.add_argument("-sep", default="\t", help="The csv-seperator")
    parser.add_argument("-r",  "--reverse", action="store_true")
    args = parser.parse_args()
    return args.res_folder, args.csv_file, args.sep, args.reverse


def process_res_folder(res_folder, dest_file, seperator):
    sub_folders = os.listdir(res_folder)
    pattern = re.compile(r"values-[a-z]{2}")
    language_value_folders = [f for f in sub_folders if re.fullmatch(pattern, f)]
    def_string_dict, indices_dict = read_def_string_file(res_folder, sub_folders)
    for f in language_value_folders:
        string_file_path = os.path.join(res_folder, f, STRING_FILENAME)
        if not os.path.exists(string_file_path):
            continue
        with open(string_file_path, "r") as string_file:
            language_brev = f[-2:]
            print(f"Found language: {language_brev}")
            string_dict = xmltodict.parse(string_file.read())["resources"]["string"]
            for value_dict in string_dict:
                if TEXT_KEY in value_dict and NAME_KEY in value_dict:
                    index = indices_dict[value_dict[NAME_KEY]]
                    def_string_dict[index][language_brev] = value_dict[TEXT_KEY]
    print(def_string_dict)
    languages = [path[-2:] for path in language_value_folders]
    with open(dest_file, "w+") as f:
        f.write(seperator.join(["key", "default"] + languages + ["extra_arguments"]) + "\n")
        for value_dict in def_string_dict:
            not_translatable = TRANSLATABLE_KEY in value_dict and value_dict[TRANSLATABLE_KEY] == "false"
            if NAME_KEY in value_dict:
                keys_in_order = [NAME_KEY, TEXT_KEY] + languages
                values = [value_dict[key] if key in value_dict else "" for key in keys_in_order]
                if not_translatable:
                    for i in range(2, len(values)):
                        values[i] = NOT_TRANSLATABLE_TEXT
                extra_data = []
                for k, v in value_dict.items():
                    if k not in keys_in_order + [TRANSLATABLE_KEY]:
                        extra_data.append(f"{k[1:]}{EXTRA_SEP_INTRA}{v}")
                values.append(EXTRA_SEP_INTER.join(extra_data))
            elif "@comment" in value_dict:
                values = ["\n%%" + value_dict["@comment"] + "%%"]
            # f.write(seperator.join([v.encode("unicode_escape").decode() for v in values]) + "\n")
            f.write(seperator.join([escape_unicodes(v) for v in values]) + "\n")


def escape_unicodes(string):
    # return string.encode("unicode_escape")\
    #     .decode()\
    #     .replace("\\xe4", "ä")\
    #     .replace("\\xf6", "ö")\
    #     .replace("\\xfc", "ü")\
    #     .replace("\\xe0", "à")\
    #     .replace("\\xe9", "é")\
    #     .replace("\\xe7", "ç")\
    #     .replace("\\xdf", "ß")
    return string.replace("\u200b", "\\u200b").replace("\u2011", "\\u2011")

def read_def_string_file(res_folder, sub_folders):
    if VALUE_FOLDER not in sub_folders:
        raise NoDefaultStringFile()
    def_value_folder = os.path.join(res_folder, VALUE_FOLDER)
    def_string_file_path = os.path.join(def_value_folder, STRING_FILENAME)
    if not os.path.exists(def_string_file_path):
        raise NoDefaultStringFile()
    with open(def_string_file_path, "r") as def_string_file:
        string_text = def_string_file.read()
        string_text = re.sub(COMMENT_PATTERN, COMMENT_XML, string_text)
        string_dict = xmltodict.parse(string_text)["resources"]["string"]
        indices_dict = {}
        for i, d in enumerate(string_dict):
            if NAME_KEY in d:
                indices_dict[d[NAME_KEY]] = i
    return string_dict, indices_dict


def process_csv_file(csv_file_path, res_folder, separator):
    string_dicts, language_brevs = get_string_dicts_from_csv(csv_file_path, separator)
    print(string_dicts)
    print(language_brevs)
    for language in language_brevs:
        create_string_xml(string_dicts, language, res_folder)



def create_string_xml(string_dicts, language, res_folder):
    is_default = language == "default"
    values_folder = os.path.join(res_folder, VALUE_FOLDER + (("-" + language) if not is_default else ""))
    if not os.path.exists(values_folder):
        os.mkdir(values_folder)
    with open(os.path.join(values_folder, STRING_FILENAME), "w+") as xml_file:
        xml_file.write('<?xml version="1.0" encoding="utf-8"?>\n')
        xml_file.write('<resources>\n')
        for string_dict in string_dicts:
            if len(string_dict) == 0:
                xml_file.write("\n")
            elif "comment" in string_dict:
                xml_file.write(f'    <!--{string_dict["comment"]}-->\n')
            else:
                if language not in string_dict or string_dict[language] == "":
                    continue
                extras = string_dict["extras"] if "extras" in string_dict else []
                if "translatable" in string_dict:
                    if not is_default:
                        continue
                    extras.append(f'translatable="{string_dict["translatable"]}"')
                extra_string = " " + " ".join(extras) if len(extras) > 0 and is_default else ""
                line_to_write = f'    <string name="{string_dict["key"]}"{extra_string}>{string_dict[language]}</string>\n'
                xml_file.write(line_to_write)
        xml_file.write("</resources>")


def get_string_dicts_from_csv(csv_file_path, separator):
    string_dicts = []
    with open(csv_file_path, "r") as csv_file:
        line = csv_file.readline()
        while line.strip() == "":
            line = csv_file.readline()
        language_brevs = line.strip().split()[2:-1]
        comment_pattern = re.compile(COMMENT_CSV_PATTERN)
        for line in csv_file.readlines():
            split = line.strip().split(sep=separator)
            comment_match = re.match(comment_pattern, line.strip())
            if len(split) == 1 and split[0] == "":
                string_dicts.append({})
                continue
            elif comment_match is not None:
                string_dicts.append({"comment": comment_match.group(1)})
                continue
            string_key, string_default, *translations_and_extra = split
            translations = translations_and_extra[:len(language_brevs)]
            extras = translations_and_extra[-1].split(EXTRA_SEP_INTER) if len(translations) < len(
                translations_and_extra) else []
            extras = ['="'.join(extra.split(EXTRA_SEP_INTRA)) + '"' for extra in extras]
            string_dict = {"key": string_key, "default": string_default, "extras": extras}
            if len(translations) > 0 and translations[0] == NOT_TRANSLATABLE_TEXT:
                # extras.append(f"translatable{EXTRA_SEP_INTRA}false")
                string_dict["translatable"] = "false"
                translations = []
            string_dict.update(zip(language_brevs, translations))
            # string_dict.update([tuple(extra.split(EXTRA_SEP_INTRA)) for extra in extras])
            string_dicts.append(string_dict)
    return string_dicts, language_brevs


if __name__ == '__main__':
    _res_folder, _csv_file, _separator, _reverse = read_arguments()
    if not _reverse:
        process_res_folder(_res_folder, _csv_file, _separator)
    else:
        process_csv_file(_csv_file, _res_folder, _separator)
