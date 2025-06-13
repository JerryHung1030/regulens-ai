import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from pypdf import PdfReader

# This assumes that the script is run from a context where 'app' is a package.
# If running this file directly for testing, sys.path adjustments might be needed.
try:
    from app.models.docs import RawDoc
except ImportError:
    # Fallback for direct execution/testing if 'app' is not in PYTHONPATH
    # This is a common pattern but might need adjustment based on actual project structure and test setup
    import sys
    # Assuming the script is in app/pipeline/, to import app.models.docs, we need to go up two levels
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.docs import RawDoc


def _calculate_file_hash(file_path: Path) -> str:
    """Reads a file in binary mode by chunks and calculates its SHA-256 hash."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except IOError as e:
        print(f"Error reading file {file_path} for hashing: {e}")
        return ""  # Return empty string or raise error


def ingest_documents(procedure_pdf_paths: List[Path], doc_type: str) -> List[RawDoc]: # Changed signature
    raw_docs: List[RawDoc] = []
    # Supported extensions check is simplified as we now only expect PDFs for procedures.
    # Control ingestion is handled elsewhere.

    if not procedure_pdf_paths:
        print("No procedure PDF paths provided.")
        return raw_docs

    for file_path in procedure_pdf_paths: # Iterate over the provided list of paths
        # Ensure it's a PDF file and exists
        if not file_path.is_file() or file_path.suffix.lower() != ".pdf":
            print(f"Skipping non-PDF or non-existent file: {file_path}")
            continue

        file_hash = _calculate_file_hash(file_path)
        if not file_hash:  # Skip if hashing failed
            print(f"Skipping file due to hashing error: {file_path}")
            continue

        content = ""
        metadata: Dict[str, Any] = {
            "original_filename": file_path.name,
            "file_type": file_path.suffix.lower(), # Should always be '.pdf'
            "errors": []
        }

        try:
            abs_file_path = file_path.resolve()

            # Simplified to only handle PDF, as this function is now specific to procedure PDFs
            try:
                reader = PdfReader(file_path)
                text_by_page = [page.extract_text() or "" for page in reader.pages]
                content = "\n".join(text_by_page)
                metadata["num_pages"] = len(reader.pages)
            except Exception as e:
                print(f"Error processing PDF {file_path}: {e}")
                metadata["errors"].append(f"PDF processing error: {str(e)}")
                content = "" # Ensure content is empty if PDF parsing fails

            # Removed .txt and .csv handling logic as this function is now for procedure PDFs.

            # Only add RawDoc if content was successfully extracted or partially extracted
            # (even with errors, some content might be there)
                raw_doc_instance = RawDoc(
                    id=file_hash,
                    source_path=abs_file_path,
                    content=content,
                    metadata=metadata.copy(),  # Use a copy for RawDoc
                    doc_type=doc_type
                )
                raw_docs.append(raw_doc_instance)

                # Create .meta.json file
                meta_json_path = file_path.parent / f"{file_path.name}.meta.json"
                meta_json_content = {
                    "file_sha256": file_hash,
                    "source_path": str(abs_file_path),
                    "original_filename": file_path.name,
                    "doc_type": doc_type,
                    "num_pages": metadata.get("num_pages"),  # Specific for PDF
                    "num_rows": metadata.get("num_rows"),   # Specific for CSV
                    "num_cols": metadata.get("num_cols"),   # Specific for CSV
                    "headers": metadata.get("headers"),     # Specific for CSV
                    "errors": metadata.get("errors")
                }
                # Remove None values for cleaner JSON
                meta_json_content = {k: v for k, v in meta_json_content.items() if v is not None}
                
                try:
                    with open(meta_json_path, 'w', encoding='utf-8') as meta_f:
                        json.dump(meta_json_content, meta_f, indent=4)
                except IOError as e:
                    print(f"Error writing .meta.json for {file_path}: {e}")
                    # This error doesn't stop the RawDoc from being created and returned

            except Exception as e:
                print(f"Unhandled exception processing file {file_path}: {e}")
                # Optionally create a RawDoc with error info even if content extraction fails catastrophically
                # For now, we skip if a major unhandled error occurs before RawDoc creation
                continue
                
    return raw_docs


if __name__ == '__main__':
    print("Starting ingestion module test...")
    # Create a temporary directory structure for testing
    temp_dir = Path("temp_ingestion_test_data")
    temp_dir.mkdir(exist_ok=True)

    sub_dir_controls = temp_dir / "controls" # Keep for potential other tests, but not used by ingest_documents directly
    sub_dir_controls.mkdir(exist_ok=True)
    sub_dir_procedures_pdfs = temp_dir / "procedures_pdfs" # New directory for test PDFs
    sub_dir_procedures_pdfs.mkdir(exist_ok=True)

    # Create dummy files
    # Control files are not ingested by this function anymore.
    # (sub_dir_controls / "control_doc1.txt").write_text("This is a control document in TXT format.", encoding="utf-8")
    
    # Create a simple PDF for testing procedures
    procedure_pdf_list: List[Path] = []
    try:
        from reportlab.pdfgen import canvas
        pdf_path1 = sub_dir_procedures_pdfs / "procedure_doc1.pdf"
        c1 = canvas.Canvas(str(pdf_path1))
        c1.drawString(100, 750, "Procedure PDF 1, Page 1.")
        c1.showPage()
        c1.drawString(100, 750, "Procedure PDF 1, Page 2.")
        c1.save()
        procedure_pdf_list.append(pdf_path1)
        print(f"Created a dummy PDF: {pdf_path1.name}")

        pdf_path2 = sub_dir_procedures_pdfs / "procedure_doc2.pdf"
        c2 = canvas.Canvas(str(pdf_path2))
        c2.drawString(100, 750, "Procedure PDF 2, Single Page.")
        c2.save()
        procedure_pdf_list.append(pdf_path2)
        print(f"Created a dummy PDF: {pdf_path2.name}")

    except ImportError:
        print("reportlab not found, skipping real PDF creation for test. Place PDFs manually for testing.")
        # Create placeholder text files if reportlab is not available, but suffix them .pdf
        placeholder_pdf1 = sub_dir_procedures_pdfs / "placeholder_proc1.pdf"
        placeholder_pdf1.write_text("This is a placeholder for procedure PDF 1.")
        procedure_pdf_list.append(placeholder_pdf1)

        placeholder_pdf2 = sub_dir_procedures_pdfs / "placeholder_proc2.pdf"
        placeholder_pdf2.write_text("This is a placeholder for procedure PDF 2.")
        procedure_pdf_list.append(placeholder_pdf2)


    # (sub_dir_procedures / "procedure_doc1.csv").write_text("header1,header2\nval1,val2\nval3,val4", encoding="utf-8") # No longer CSV
    # (sub_dir_procedures / "corrupted.txt").write_bytes(b'\x80\x90\xa0') # No longer TXT

    # print(f"\nIngesting 'control' documents from: {sub_dir_controls}") # Controls no longer ingested here
    # control_docs = ingest_documents(sub_dir_controls, "control") # This would now be an error if not a list of Paths
    # for doc in control_docs:
    #     print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
    #     meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
    #     print(f"  Meta JSON exists: {meta_json_file.exists()}")
    #     if meta_json_file.exists():
    #         with open(meta_json_file, 'r') as f_meta:
    #             print(f"  Meta JSON content: {json.load(f_meta)}")

    print(f"\nIngesting 'procedure' PDF documents from list: {procedure_pdf_list}")
    procedure_docs = ingest_documents(procedure_pdf_list, "procedure") # Pass list of paths
    for doc in procedure_docs:
        print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
        meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
        print(f"  Meta JSON exists: {meta_json_file.exists()}")
        if meta_json_file.exists():
            with open(meta_json_file, 'r') as f_meta:
                print(f"  Meta JSON content: {json.load(f_meta)}")

    # Test with a non-existent directory (now an empty list or list with non-existent paths)
    print("\nIngesting from a list with a non-existent PDF path:")
    non_existent_pdf_path = Path("non_existent_dir_test/non_existent.pdf") # This path won't exist
    non_existent_docs = ingest_documents([non_existent_pdf_path], "error_test")
    print(f"  Number of documents found: {len(non_existent_docs)}")

    print("\nIngesting from an empty list:")
    empty_list_docs = ingest_documents([], "empty_test")
    print(f"  Number of documents found: {len(empty_list_docs)}")


    # Clean up (optional)
    # import shutil
    # print(f"\nCleaning up temporary test directory: {temp_dir}")
    # shutil.rmtree(temp_dir)
    print("\nIngestion module test finished.")
