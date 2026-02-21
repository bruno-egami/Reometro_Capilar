import zipfile
import sys
import xml.etree.ElementTree as ET

def extract(filepath, outpath):
    try:
        with zipfile.ZipFile(filepath) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = '\n'.join([node.text for node in root.findall('.//w:t', ns) if node.text])
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(text)
            print('Extraction successful:', outpath)
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    extract(r'd:\GitHub\Reometro_Capilar\Analise-melhorias\Revisao_Modelamento_Matematico.docx', r'd:\GitHub\Reometro_Capilar\Analise-melhorias\Revisao_Modelamento_Matematico.txt')
