import PyPDF2
import os

# Check if file exists
pdf_file = 'Gaurav-Pant-Resume-2025-1.pdf'
if not os.path.exists(pdf_file):
    print(f"❌ Error: File '{pdf_file}' not found!")
    print("Make sure the PDF file is in the same directory as this script.")
else:
    try:
        with open(pdf_file, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Check if PDF has pages
            if len(reader.pages) == 0:
                print("❌ Error: PDF has no pages!")
            else:
                print("✅ PDF loaded successfully!")
                print(f"📄 Number of pages: {len(reader.pages)}")
                
                # Print metadata
                print("\n📋 PDF Metadata:")
                print(reader.metadata)
                
                # Extract text from first page
                print("\n📝 Text from first page:")
                text = reader.pages[0].extract_text()
                if text.strip():
                    print(text)
                else:
                    print("No text found on first page (might be image-based)")
                    
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        print("Possible issues:")
        print("- PDF is password protected")
        print("- PDF is corrupted")
        print("- PDF is not a valid PDF file")






