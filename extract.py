import zipfile
import xml.etree.ElementTree as ET

def extract(docx_path):
    z = zipfile.ZipFile(docx_path)
    xml_content = z.read('word/document.xml')
    tree = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    lines = []
    for p in tree.findall('.//w:p', ns):
        texts = [t.text for r in p.findall('.//w:r', ns) for t in r.findall('.//w:t', ns) if t.text]
        if texts:
            lines.append(''.join(texts))
    return '\n'.join(lines)

with open('extracted_text.txt', 'w', encoding='utf-8') as f:
    f.write(extract(r'D:\GitHub\Reometro_Capilar\Analise-melhorias\Analise_Completa_Reometro_Capilar_v2.docx'))
