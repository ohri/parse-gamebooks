import pdfplumber

with pdfplumber.open('housea.pdf') as pdf:
    first_page = pdf.pages[0]
    text = first_page.extract_text()

    lines = text.split('\n')

    # Print the substitutions and inactive sections
    for i, line in enumerate(lines):
        if i >= 26 and i <= 38:  # Substitutions to inactive section
            print(f"{i:3}: {line}")
