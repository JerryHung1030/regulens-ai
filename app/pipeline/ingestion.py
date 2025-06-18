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


def ingest_documents(procedure_pdf_paths: List[Path], doc_type: str) -> List[RawDoc]:
    raw_docs: List[RawDoc] = []

    if not procedure_pdf_paths:
        print("No procedure PDF paths provided.")
        return raw_docs

    for file_path in procedure_pdf_paths:
        if not file_path.is_file() or file_path.suffix.lower() not in [".txt", ".md"]:
            print(f"Skipping non-TXT/MD or non-existent file: {file_path}")
            continue

        file_hash = _calculate_file_hash(file_path)
        if not file_hash:
            print(f"Skipping file due to hashing error: {file_path}")
            continue

        content = ""
        metadata: Dict[str, Any] = {
            "original_filename": file_path.name,
            "file_type": file_path.suffix.lower(),
            "errors": []
        }

        try:
            abs_file_path = file_path.resolve()

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Optionally, add line count to metadata if useful
                # metadata["num_lines"] = content.count('\n') + 1
            except Exception as e:
                print(f"Error processing TXT {file_path}: {e}")
                metadata["errors"].append(f"TXT processing error: {str(e)}")
                content = ""

            raw_doc_instance = RawDoc(
                id=file_hash,
                source_path=abs_file_path,
                content=content,
                metadata=metadata.copy(),
                doc_type=doc_type
            )
            raw_docs.append(raw_doc_instance)

            meta_json_path = file_path.parent / f"{file_path.name}.meta.json"
            meta_json_content = {
                "file_sha256": file_hash,
                "source_path": str(abs_file_path),
                "original_filename": file_path.name,
                "doc_type": doc_type,
                # "num_pages": metadata.get("num_pages"), # Removed
                "num_rows": metadata.get("num_rows"),
                "num_cols": metadata.get("num_cols"),
                "headers": metadata.get("headers"),
                "errors": metadata.get("errors")
            }
            meta_json_content = {k: v for k, v in meta_json_content.items() if v is not None}
            # Ensure metadata dictionary itself doesn't carry over "num_pages"
            if "num_pages" in metadata:
                del metadata["num_pages"]
            
            try:
                with open(meta_json_path, 'w', encoding='utf-8') as meta_f:
                    json.dump(meta_json_content, meta_f, indent=4)
            except IOError as e:
                print(f"Error writing .meta.json for {file_path}: {e}")

        except Exception as e:
            print(f"Unhandled exception processing file {file_path}: {e}")
            continue

    return raw_docs


if __name__ == '__main__':
    print("Starting ingestion module test...")
    # Create a temporary directory structure for testing
    temp_dir = Path("temp_ingestion_test_data")
    temp_dir.mkdir(exist_ok=True)

    sub_dir_external_regulations = temp_dir / "external_regulations" # Keep for potential other tests, but not used by ingest_documents directly
    sub_dir_external_regulations.mkdir(exist_ok=True)
    sub_dir_procedures_pdfs = temp_dir / "procedures_pdfs" # New directory for test PDFs
    sub_dir_procedures_pdfs.mkdir(exist_ok=True)

    # Create dummy files
    # ExternalRegulation files are not ingested by this function anymore.
    # (sub_dir_external_regulations / "external_regulation_doc1.txt").write_text("This is a external_regulation document in TXT format.", encoding="utf-8")
    
    # Create simple TXT files for testing procedures
    procedure_txt_list: List[Path] = []
    txt_path1 = sub_dir_procedures_pdfs / "procedure_doc1.txt"
    txt_path1.write_text("This is the content of procedure_doc1.txt.\nIt has multiple lines.", encoding="utf-8")
    procedure_txt_list.append(txt_path1)
    print(f"Created a dummy TXT: {txt_path1.name}")

    txt_path2 = sub_dir_procedures_pdfs / "procedure_doc2.txt"
    txt_path2.write_text("This is procedure_doc2.txt.", encoding="utf-8")
    procedure_txt_list.append(txt_path2)
    print(f"Created a dummy TXT: {txt_path2.name}")
    
    # Create a TXT file with non-utf-8 content to test error handling
    error_txt_path = sub_dir_procedures_pdfs / "error_doc.txt"
    try:
        with open(error_txt_path, 'wb') as f_err:
            f_err.write(b'\xff\xfe\x00\x00This is not valid UTF-8') # Example: UTF-16 BOM with non-UTF-8 chars
        procedure_txt_list.append(error_txt_path)
        print(f"Created a dummy TXT with invalid encoding: {error_txt_path.name}")
    except Exception as e_create:
        print(f"Could not create error_doc.txt for testing: {e_create}")


    # (sub_dir_procedures / "procedure_doc1.csv").write_text("header1,header2\nval1,val2\nval3,val4", encoding="utf-8")
    # (sub_dir_procedures / "corrupted.txt").write_bytes(b'\x80\x90\xa0')

    # print(f"\nIngesting 'external_regulation' documents from: {sub_dir_external_regulations}")
    # external_regulation_docs = ingest_documents(sub_dir_external_regulations, "external_regulation")
    # for doc in external_regulation_docs:
    #     print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
    #     meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
    #     print(f"  Meta JSON exists: {meta_json_file.exists()}")
    #     if meta_json_file.exists():
    #         with open(meta_json_file, 'r') as f_meta:
    #             print(f"  Meta JSON content: {json.load(f_meta)}")

    print(f"\nIngesting 'procedure' TXT documents from list: {procedure_txt_list}")
    procedure_docs = ingest_documents(procedure_txt_list, "procedure") # Pass list of paths
    for doc in procedure_docs:
        print(f"  RawDoc ID: {doc.id}, Source: {doc.source_path.name}, Type: {doc.doc_type}, Metadata: {doc.metadata}")
        meta_json_file = doc.source_path.parent / f"{doc.source_path.name}.meta.json"
        print(f"  Meta JSON exists: {meta_json_file.exists()}")
        if meta_json_file.exists():
            with open(meta_json_file, 'r') as f_meta:
                loaded_meta = json.load(f_meta)
                print(f"  Meta JSON content: {loaded_meta}")
                assert "num_pages" not in loaded_meta # Ensure num_pages is not in the meta file

    # Test with a non-existent directory (now an empty list or list with non-existent paths)
    print("\nIngesting from a list with a non-existent TXT path:")
    non_existent_txt_path = Path("non_existent_dir_test/non_existent.txt") # This path won't exist
    non_existent_docs = ingest_documents([non_existent_txt_path], "error_test")
    print(f"  Number of documents found: {len(non_existent_docs)}")

    print("\nIngesting from an empty list:")
    empty_list_docs = ingest_documents([], "empty_test")
    print(f"  Number of documents found: {len(empty_list_docs)}")


    # Clean up (optional)
    # import shutil
    # print(f"\nCleaning up temporary test directory: {temp_dir}")
    # shutil.rmtree(temp_dir)
    print("\nIngestion module test finished.")
