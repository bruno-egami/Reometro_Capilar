import zipfile
import xml.etree.ElementTree as ET

try:
    with zipfile.ZipFile(r'd:\GitHub\Reometro_Capilar\Analise-melhorias\Revisao_Implementacao_PlotStyle.docx') as z:
        xml_content = z.read('word/document.xml')
        root = ET.fromstring(xml_content)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = '\n'.join([node.text for node in root.findall('.//w:t', ns) if node.text])
        with open(r'd:\GitHub\Reometro_Capilar\Analise-melhorias\Revisao_Implementacao_PlotStyle.txt', 'w', encoding='utf-8') as f:
            f.write(text)
        print('Extraction successful.')
except Exception as e:
    print('Error:', e)
