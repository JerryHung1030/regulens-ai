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
        return "" # Return empty string or raise error


def ingest_documents(input_dir: Path, doc_type: str) -> List[RawDoc]:
    raw_docs: List[RawDoc] = []
    supported_extensions = [".pdf", ".txt", ".csv"]

    if not input_dir.is_dir():
        print(f"Error: Input directory {input_dir} does not exist or is not a directory.")
        return raw_docs

    for file_path in input_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            file_hash = _calculate_file_hash(file_path)
            if not file_hash: # Skip if hashing failed
                continue

            content = ""
            metadata: Dict[str, Any] = {
                "original_filename": file_path.name,
                "file_type": file_path.suffix.lower(),
                "errors": []
            }
            
            try:
                abs_file_path = file_path.resolve()

                if file_path.suffix.lower() == ".pdf":
                    try:
                        reader = PdfReader(file_path)
                        text_by_page = [page.extract_text() or "" for page in reader.pages]
                        content = "\n".join(text_by_page)
                        metadata["num_pages"] = len(reader.pages)
                        # Storing all text_by_page might be too verbose for .meta.json,
                        # but useful in RawDoc.metadata
                        # metadata["text_by_page"] = text_by_page 
                    except Exception as e:
                        print(f"Error processing PDF {file_path}: {e}")
                        metadata["errors"].append(f"PDF processing error: {str(e)}")
                        content = "" # Ensure content is empty if PDF parsing fails

                elif file_path.suffix.lower() == ".txt":
                    try:
                        content = file_path.read_text(encoding="utf-8")
                    except UnicodeDecodeError as e:
                        print(f"Encoding error reading TXT {file_path} as UTF-8: {e}. Trying with 'latin-1'.")
                        metadata["errors"].append(f"UTF-8 decoding error: {str(e)}")
                        try:
                            content = file_path.read_text(encoding="latin-1")
                            metadata["encoding_used"] = "latin-1"
                        except Exception as e_latin1:
                            print(f"Error reading TXT {file_path} with latin-1: {e_latin1}")
                            metadata["errors"].append(f"Latin-1 decoding error: {str(e_latin1)}")
                            content = "" # Ensure content is empty
                    except Exception as e:
                        print(f"Error reading TXT {file_path}: {e}")
                        metadata["errors"].append(f"TXT reading error: {str(e)}")
                        content = ""


                elif file_path.suffix.lower() == ".csv":
                    try:
                        df = pd.read_csv(file_path)
                        content = df.to_csv(index=False) # Consistent string representation
                        metadata["num_rows"] = len(df)
                        metadata["num_cols"] = len(df.columns)
                        metadata["headers"] = list(df.columns)
                    except Exception as e:
                        print(f"Error processing CSV {file_path}: {e}")
                        metadata["errors"].append(f"CSV processing error: {str(e)}")
                        content = ""

                # Only add RawDoc if content was successfully extracted or partially extracted
                # (even with errors, some content might be there)
                raw_doc_instance = RawDoc(
                    id=file_hash,
                    source_path=abs_file_path,
                    content=content,
                    metadata=metadata.copy(), # Use a copy for RawDoc
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
                    "num_pages": metadata.get("num_pages"), # Specific for PDF
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

    sub_dir_controls = temp_dir / "controls"
    sub_dir_controls.mkdir(exist_ok=True)
    sub_dir_procedures = temp_dir / "procedures"
    sub_dir_procedures.mkdir(exist_ok=True)

    # Create dummy files
    (sub_dir_controls / "control_doc1.txt").write_text("This is a control document in TXT format.", encoding="utf-8")
    (sub_dir_controls / "control_doc2.pdf").write_text("Dummy PDF content (not a real PDF for this test script). For real PDF test, place a PDF here.")
    
    # Create a simple PDF for testing (requires reportlab or manual creation)
    # For simplicity, this test won't create a real PDF, but pypdf will attempt to read it.
    # Actual PDF testing should be done with a valid PDF file.
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(sub_dir_controls / "real_control.pdf"))
        c.drawString(100, 750, "This is page 1 of a real PDF.")
        c.showPage()
        c.drawString(100, 750, "This is page 2 of a real PDF.")
        c.save()
        print("Created a dummy PDF: real_control.pdf")
    except ImportError:
        print("reportlab not found, skipping real PDF creation for test. Place a PDF manually for testing.")
        (sub_dir_controls / "real_control.pdf").write_text("This is a placeholder for a PDF.")


    (sub_dir_procedures / "procedure_doc1.csv").write_text("header1,header2\nval1,val2\nval3,val4", encoding="utf-8")
    (sub_dir_procedures / "corrupted.txt").write_bytes(b'\x80\x90\xa0') # Invalid UTF-8

    print(f"\nIngesting 'control' documents from: {sub_dir_controls}")
    control_docs = ingest_documents(sub_dir_controls, "control")
    for doc in control_docs:
        print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
        meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
        print(f"  Meta JSON exists: {meta_json_file.exists()}")
        if meta_json_file.exists():
             with open(meta_json_file, 'r') as f_meta:
                 print(f"  Meta JSON content: {json.load(f_meta)}")


    print(f"\nIngesting 'procedure' documents from: {sub_dir_procedures}")
    procedure_docs = ingest_documents(sub_dir_procedures, "procedure")
    for doc in procedure_docs:
        print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
        meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
        print(f"  Meta JSON exists: {meta_json_file.exists()}")
        if meta_json_file.exists():
             with open(meta_json_file, 'r') as f_meta:
                 print(f"  Meta JSON content: {json.load(f_meta)}")

    # Test with a non-existent directory
    print(f"\nIngesting from non-existent directory:")
    non_existent_docs = ingest_documents(Path("non_existent_dir_test"), "error_test")
    print(f"  Number of documents found: {len(non_existent_docs)}")

    # Clean up (optional)
    # import shutil
    # print(f"\nCleaning up temporary test directory: {temp_dir}")
    # shutil.rmtree(temp_dir)
    print("\nIngestion module test finished.")
