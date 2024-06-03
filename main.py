import argparse
import math

from selenium import webdriver
from bs4 import BeautifulSoup, Tag, Comment
import codecs
import time
import re

from selenium.webdriver.common.by import By

errors: list[str] = []

is_fixed = False


def get_content_and_add_to_dict(driver: webdriver.Chrome, y: int, word_list: list[(list[str], str)]):
    # SNATCH WEBPAGE
    driver.get(f"https://ordbokene.no/bm/{y}")

    global is_fixed
    if not is_fixed:
        buttons = driver.find_elements(By.CLASS_NAME, "v-size--small")
        buttons[2].click()
        driver.find_element(By.CLASS_NAME, 'v-list-item').click()
        is_fixed = True

    lookup = None
    while lookup is None:
        soup = BeautifulSoup(driver.page_source, "html.parser")

        lookup = soup.find('span', attrs={"class": "lookup"})

        if lookup is None:
            f04 = soup.find('h1', attrs={"id": "result0"})
            if f04 is not None:
                error_string = f"404 ON PAGE: {x}"
                errors.append(error_string)
                print(error_string)
                return

            e = soup.find(string=re.compile("Det har oppstått"), recursive=True)
            if e is not None:
                error_string = f"ERROR ON PAGE: {x}"
                errors.append(error_string)
                print(error_string)
                return

    # words_raw = lookup.find('h3').text.strip()
    # split1 = words_raw.split(',')
    # for word in split1:
    #     split2 = word.split()
    #     true_word = split2[0]
    #     if len(split2) > 1:
    #         def_nr = split2[1]
    #
    #     words.append(true_word)

    words: list[str] = []

    h3 = lookup.find('h3')

    child: Tag
    for child in h3.children:
        words_raw = child.find_all('span', class_=None)
        for word in words_raw:
            tag = soup.new_tag('span')
            tag.insert(0, word)
            words.append(tag.text)

    table = soup.find('table', class_="infl-table md")
    if table is not None:
        boyninger = table.find_all('td', class_="infl-cell")
        for boye in boyninger:
            print(boye.text)

    def_nr = ""
    def_elem = lookup.find(class_="hgno")
    if def_elem is not None:
        def_nr = def_elem.text.strip()

    # FIND TYPE AND GENDER
    has_type = False

    type_and_gender = lookup.find('span', attrs={"class": "subheader"})
    if type_and_gender is not None:
        has_type = True
        type_span = type_and_gender.find('span')
        gender = type_span.next_sibling.text.strip()
        type_ = type_span.text.strip()

    # FIND DEFINITIONS, USAGE AND EXPRESSIONS
    word_string = "<h3>"
    ii = 1
    for word in words:
        word_string += f"{word}"
        if def_nr != "":
            word_string += f"<sub>{def_nr}</sub>"
        if ii < len(words):
            word_string += ", "
        ii += 1

    word_string += "</h3>"

    if has_type:
        type_string = f"{type_.upper()} "
        if gender != "":
            type_string += f"<i>{gender}</i>"

        html_string = f"<section>{word_string}{type_string}<p></p></section>"
    else:
        html_string = f"<section>{word_string}<p></p></section>"

    sections = soup.find_all('section')

    section: Tag
    for section in sections:
        class_name = section['class']
        match class_name:
            case ['definitions']:
                html_string += str(clean_definitions(section))
                print("Found definition.")
            case ['pronunciation']:
                html_string += str(clean_pronunciation(section))
                print("Found pronunciation.")
            case ['etymology']:
                html_string += str(clean_etymology(section))
                print("Found etymology.")
            case ['expressions']:
                html_string += str(clean_expressions(section))
                print("Found expressions.")
            case _:
                print(f"Unexpected section found! : {class_name}")

    html_string = html_string.replace("ˊ", "&#180;")

    # html_string += "<section><br><h5><i>Bokmålsordboka.</i> Språkrådet og Universitetet i Bergen. " \
    #                "(hentet 13.09.2022).</h5><br></section>"

    print(html_string)
    word_list.append((words, html_string))


def get_examples(level: Tag):
    return level.find('ul', attrs={"class": "examples"}, recursive=True)


def get_explanations(level: Tag) -> list[(Tag, Tag, bool)]:
    explanations = level.find_all('ul', attrs={"class": "explanations"}, recursive=True)

    explanation_list: list[(Tag, Tag, bool)] = []
    examples: Tag = Tag(None, name='span')
    empty: bool = True

    explanation: Tag
    for explanation in explanations:
        sibling = explanation.find_next_sibling('div')
        if explanation.text == "" and sibling is None:
            continue

        if sibling is not None:
            examples = get_examples(sibling)
            empty = False

        explanation_list.append((explanation, examples, empty))

    return explanation_list


def clean_definitions(sec: Tag) -> Tag:
    level1 = sec.find('li', attrs={"class": "definition level1"})
    explanations_and_examples = get_explanations(level1)

    content = BeautifulSoup("", "html.parser")
    ordered_list = content.new_tag(name='ol')

    ii = 100
    for exp, exa, empty in explanations_and_examples:
        ii -= 1
        exp = remove_certain_tags(remove_attr(exp))
        exa = remove_certain_tags(remove_attr(exa))

        content.append(exp)

        if not empty:
            tag = content.new_tag(name='h5')
            tag.append(content.new_string("Eksempel"))
            content.append(tag)

            exa["class"] = "example"
            content.append(exa)

        content.append(content.new_tag(name='p'))

        span = content.new_tag(name='span')
        span.insert(0, content)

        list_item = content.new_tag(name='li')
        list_item.insert(0, span)

        ordered_list.insert(ii, list_item)

    definition = content.new_tag(name='h4')
    definition.append(content.new_string("BETYDNING OG BRUK"))

    section = content.new_tag(name='section')
    section.insert(0, definition)
    section.insert(1, ordered_list)

    # print(section)
    return section


def clean_pronunciation(sec: Tag) -> Tag:
    pronunciation = sec.find('li', attrs={"class": "pronunciation"}, recursive=True)

    soup = BeautifulSoup("", "html.parser")

    header = soup.new_tag('h4', attrs={"style": "display: inline-block;"})
    header.append(soup.new_string("UTTALE"))

    span = soup.new_tag('span', attrs={"class": "inline"})
    span.insert(0, remove_certain_tags(remove_attr(pronunciation)))
    span.find('li').unwrap()

    section = soup.new_tag('section')
    section.insert(0, header)
    section.insert(1, span)

    # print(section)
    return section


def clean_etymology(sec: Tag) -> Tag:
    etymology = sec.find('li', attrs={"class": "etymology_language"}, recursive=True)
    if etymology is None:
        etymology = sec.find('li', attrs={"class": "etymology_reference"}, recursive=True)
    if etymology is None:
        etymology = sec.find('li', attrs={"class": "etymology_litt"}, recursive=True)

    soup = BeautifulSoup("", "html.parser")

    header = soup.new_tag('h4', attrs={"style": "display: inline-block;"})
    header.append(soup.new_string("OPPHAV"))

    span = soup.new_tag('span', attrs={"class": "inline"})
    span.insert(0, remove_certain_tags(remove_attr(etymology)))
    span.find('li').unwrap()

    section = soup.new_tag('section')
    section.insert(0, header)
    section.insert(1, span)

    # print(section)
    return section


def get_expressions_and_explanations(level: Tag) -> list[(str, Tag, Tag, bool)]:
    explanations = level.find_all('ul', attrs={"class": "explanations"}, recursive=True)

    explanation_list: list[(str, Tag, Tag, bool)] = []
    examples: Tag = Tag(None, name='span')
    empty: bool = True

    explanation: Tag
    for explanation in explanations:
        if explanation.text == "":
            continue

        expression: str = explanation.find_parent('li', attrs={"class": "sub_article"})\
            .find('span', attrs={"class": "sub_article_header"}).text

        sibling = explanation.find_next_sibling('div')
        if sibling is not None:
            examples = get_examples(sibling)
            empty = False

        explanation_list.append((expression, explanation, examples, empty))

    return explanation_list


def clean_expressions(sec: Tag) -> Tag:
    explanations_and_examples = get_expressions_and_explanations(sec)

    content = BeautifulSoup("", "html.parser")
    ordered_list = content.new_tag(name='ol', attrs={"style": "list-style:none"})

    ii = 100
    for spres, exp, exa, empty in explanations_and_examples:
        ii -= 1
        exp = remove_certain_tags(remove_attr(exp))
        exa = remove_certain_tags(remove_attr(exa))

        header = content.new_tag('h4', attrs={"class": "uttrykk"})
        header.append(content.new_string(spres))
        content.append(header)
        content.append(exp)

        if not empty:
            tag = content.new_tag(name='h5')
            tag.append(content.new_string("Eksempel"))
            content.append(tag)

            exa["class"] = "example"
            content.append(exa)

        content.append(content.new_tag(name='p'))

        span = content.new_tag(name='span')
        span.insert(0, content)

        list_item = content.new_tag(name='li')
        list_item.insert(0, span)

        ordered_list.insert(ii, list_item)

    definition = content.new_tag(name='h4')
    definition.append(content.new_string("FASTE UTTRYKK"))

    section = content.new_tag(name='section')
    section.insert(0, definition)
    section.insert(1, ordered_list)

    # print(section)
    return section


def remove_attr(content: Tag) -> Tag:
    content.attrs = {}

    tag: Tag
    for tag in content.find_all(True, recursive=True):
        tag.attrs = {}

    return content


def remove_certain_tags(content: Tag):
    for hyperlink in content.find_all('a'):
        hyperlink.unwrap()

    for comment in content.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    for span in content.find_all('span'):
        span.unwrap()

    return content


head = "<head><style type=\"text/css\">" \
           "*{margin-top:1px;margin-bottom:1px}" \
           "p{margin-top:10px;margin-bottom:10px}" \
           ".inline{margin-left:30px}" \
           ".example{list-style:none;margin-left: 20px;}" \
           ".uttrykk{margin-left:-20px}" \
           "h5{margin-left:40px;margin-top:5px}" \
           "q{font-style:italic;quotes:none}" \
           "</style></head>"


def write_content_to_xml(words: list[(str, str)], identifier: str):
    doc_name = f"nob_dict_{identifier}.xml"
    file = codecs.open("output\\"+doc_name, 'w', "utf-8")

    file.write("<?xml version = \"1.0\" encoding = \"UTF-8\"?>\n\n")

    file.write("<dict>\n\n")
    for key, html in words:
        file.write("\t<entry>\n")
        file.write(f"\t\t<key>{key}</key>\n")
        file.write(f"\t\t<def><![CDATA[{head}{html}]]></def>\n")
        file.write("\t</entry>\n\n")
    file.write("</dict>")

    file.close()
    print(f"'{doc_name}' file has been written!")


def write_content_to_df(words: list[(list[str], str)], identifier: str):
    doc_name = f"nob_dict_{identifier}.df"
    file = codecs.open("output\\"+doc_name, 'w', "utf-8")

    for words_list, html in words:
        words_string = f"@ {words_list[0]}\n"
        for ii in range(1, len(words_list)):
            words_string += f"& {words_list[ii]}\n"

        file.write(f"{words_string}::\n<html>{head}{html}\n\n")

    file.close()
    print(f"'{doc_name}' file has been written!")


# start: int = 1
# end: int = 69759
start: int = 6739
end: int = 6739

words_per_file: int = 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("start_index", type=int, nargs='?', default=start)
    parser.add_argument("end_index", type=int, nargs='?', default=end)
    parser.add_argument("words_per_file", type=int, nargs='?', default=words_per_file)
    args = parser.parse_args()

    total: int = args.end_index - args.start_index + 1

    time_when_started = time.time()

    chrome = webdriver.Chrome()
    current_word_list: list[(list[str], str)] = []

    file_start = args.start_index

    i: int = 0
    for x in range(args.start_index, args.end_index+1):
        i += 1
        get_content_and_add_to_dict(chrome, x, current_word_list)

        if len(current_word_list) >= args.words_per_file:
            # write_content_to_xml(current_word_list, f"{file_start}_to_{args.start_index+i-1}")
            write_content_to_df(current_word_list, f"{file_start}_to_{args.start_index+i-1}")
            file_start = args.start_index+i
            current_word_list = []

        completion = math.floor(i / total * 100)  # 0-100%
        print(f"Progress: [{('■' * completion)}{' ' * (100-completion)}] {completion}%  {x}/{args.end_index}")

    if len(current_word_list) > 0:
        # write_content_to_xml(current_word_list, f"{file_start}_to_{args.start_index+i-1}")
        write_content_to_df(current_word_list, f"{file_start}_to_{args.start_index+i-1}")

    time_when_ended = time.time()

    if len(errors) > 0:
        print("Error(s):")
        for error in errors:
            print(f"\t{error}")

    print(f"Elapsed time: {time_when_ended-time_when_started}")

    chrome.close()
