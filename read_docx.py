import docx
doc = docx.Document(r'C:\Users\athit\Skeptic Engine\Skeptic_Engine_Narration_Script.docx')
for i, para in enumerate(doc.paragraphs):
    if para.text.strip():
        print(f'[{i}] {para.style.name}: {para.text}')
