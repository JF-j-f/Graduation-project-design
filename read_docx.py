import docx

doc = docx.Document(r'f:\Graduation-project-design\Document\Word\基于大数据技术的个性化音乐推荐系统的设计与实现（V10）.docx')
in_ch6 = False
text = []

for p in doc.paragraphs:
    if '第六章' in p.text and '系统评估' in p.text:
        in_ch6 = True
    if in_ch6:
        text.append(p.text)
    if in_ch6 and '结论' in p.text and '第七章' in p.text:
        break

with open(r'f:\Graduation-project-design\temp_ch6.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(text))
