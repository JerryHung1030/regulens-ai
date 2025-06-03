import re
import unicodedata
from typing import List

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.docs import RawDoc, NormDoc
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.docs import RawDoc, NormDoc

# Pre-compile regex patterns for efficiency
# Pattern for multiple spaces/tabs
RE_MULTI_SPACE_TAB = re.compile(r'[ \t]+')
# Pattern for section numbers like "1.", "1.2.", "A.1.", "(A.1.)" etc. at the start of a line
RE_SECTION_NUMBERS = re.compile(r'^\s*([(\[]?\w+([.]\w+)*[.)\]]?\s*)+')
# Pattern for titles like "Chapter X", "Section Y", "Part Z", "Article 1" etc. at the start of a line
RE_SECTION_TITLES = re.compile(r'^\s*(Chapter|Section|Part|Article)\s+[\w\d\-.]+\s*[:\-–]?\s*', flags=re.IGNORECASE)
# Pattern for consolidating multiple newlines
RE_MULTI_NEWLINE = re.compile(r'\n\s*\n+')


def normalize_document(raw_doc: RawDoc) -> NormDoc:
    text = raw_doc.content
    normalization_steps_applied = []

    # 1. Unicode Normalization
    try:
        text = unicodedata.normalize('NFC', text)
        normalization_steps_applied.append("unicode_nfc")
    except Exception as e:
        print(f"Error during Unicode normalization for doc {raw_doc.id}: {e}")
        # Continue with original text if normalization fails

    # 2. Initial whitespace cleanup (consolidate spaces/tabs)
    text = RE_MULTI_SPACE_TAB.sub(' ', text)
    normalization_steps_applied.append("space_tab_consolidation")

    lines = text.splitlines()
    processed_lines: List[str] = []
    identified_sections_basic: List[str] = []

    for line in lines:
        stripped_line = line.strip()

        # If line is empty after stripping, skip it to consolidate blank lines later
        if not stripped_line:
            processed_lines.append("")  # Keep it as an empty string to allow newline consolidation
            continue

        # 3. Section Number/Title Cleaning
        cleaned_line = stripped_line
        # Remove section numbers first
        cleaned_line = RE_SECTION_NUMBERS.sub('', cleaned_line).strip()
        # Then remove section titles
        cleaned_line = RE_SECTION_TITLES.sub('', cleaned_line).strip()
        
        # Heuristic for basic section identification:
        # If the line became empty after cleaning, and original was not empty,
        # or if the original line was ALL CAPS and relatively short.
        is_potential_section = False
        if (not cleaned_line and stripped_line) or \
           (stripped_line.isupper() and len(stripped_line) < 150 and len(stripped_line) > 3):  # Min length for ALL CAPS
            # Further check: if it contained mostly section-like patterns
            if RE_SECTION_NUMBERS.match(stripped_line) or RE_SECTION_TITLES.match(stripped_line) or stripped_line.isupper():
                identified_sections_basic.append(stripped_line)
                is_potential_section = True
        
        # Only add non-empty lines after cleaning.
        # If it was identified as a section, we might choose to not add it to main content,
        # or add it if sections are part of the readable flow. For now, let's add it.
        # If we don't want section headers in the main text_content, we'd `continue` here if is_potential_section.
        if cleaned_line:
            processed_lines.append(cleaned_line)
        elif is_potential_section and not cleaned_line: 
            # If it was ONLY a section header and now empty, don't add an empty line
            pass

    normalization_steps_applied.append("leading_trailing_strip_lines")
    if "RE_SECTION_NUMBERS" not in str(normalization_steps_applied):  # Avoid duplicate from loop
        normalization_steps_applied.append("basic_section_number_title_removal")

    # Reconstruct text: join lines with single newline
    final_text_content = "\n".join(processed_lines)
    
    # Consolidate multiple newlines (e.g., from empty lines processed above)
    # Replace sequences of one or more blank lines (now single newlines from join) with a single newline.
    # Effectively, this means multiple original blank lines become one.
    final_text_content = RE_MULTI_NEWLINE.sub('\n', final_text_content).strip()
    normalization_steps_applied.append("extra_newline_consolidation")

    # 5. NormDoc Creation
    norm_doc_id = f"norm_{raw_doc.id}"
    metadata = raw_doc.metadata.copy()
    metadata["normalization_applied"] = normalization_steps_applied
    if identified_sections_basic:
        metadata["basic_sections_identified_count"] = len(identified_sections_basic)

    return NormDoc(
        id=norm_doc_id,
        raw_doc_id=raw_doc.id,
        text_content=final_text_content,
        sections=identified_sections_basic,
        metadata=metadata,
        doc_type=raw_doc.doc_type
    )


if __name__ == '__main__':
    from pathlib import Path

    print("Starting normalization module test...")

    raw_doc_sample_1 = RawDoc(
        id="test_raw_doc_123",
        source_path=Path("dummy/sample1.txt"),
        content="  1. Introduction  \n\nThis is   a test. \n\n\nCHAPTER 2: METHODS\n  ARTICLE 1 - Definitions \n 2.1 Sub Method (a) item one \n   This is more text.  \n\n\n   Another paragraph. \n\nSECTION III - RESULTS\n (3.1) Result A\n\n  \n \t Leading and trailing spaces line. \t  \nALL CAPS SECTION HEADER",
        metadata={"original_filename": "sample1.txt", "author": "tester"},
        doc_type="control"
    )

    raw_doc_sample_2 = RawDoc(
        id="test_raw_doc_456",
        source_path=Path("dummy/sample2.txt"),
        content="\t\tFirst line with tabs.\n\n1.2.3. Complex Section Number\nThis text is under complex section.\n\n   \n  Another line, indented.\n\nCHAPTER 1\nOnly a chapter title.",
        metadata={"original_filename": "sample2.txt"},
        doc_type="procedure"
    )
    
    raw_doc_sample_3_unicode = RawDoc(
        id="test_raw_doc_789_unicode",
        source_path=Path("dummy/sample3_unicode.txt"),
        content="Th\u00e9 Qu\u00efck Br\u00f6wn F\u00f6x\n\nN\u00e3ive approach vs. \u004e\u0061\u00ef\u0076\u0065 approach.",  # NFC vs NFD
        metadata={"original_filename": "sample3_unicode.txt"},
        doc_type="evidence"
    )

    test_docs = [raw_doc_sample_1, raw_doc_sample_2, raw_doc_sample_3_unicode]

    for i, raw_doc_sample in enumerate(test_docs):
        print(f"\n--- Normalizing Sample {i + 1} (ID: {raw_doc_sample.id}) ---")
        norm_doc_output = normalize_document(raw_doc_sample)
        print(f"Original Content:\n'''{raw_doc_sample.content}'''")
        print(f"\nNormalized Document (ID: {norm_doc_output.id}):")
        print(f"Text Content:\n'''{norm_doc_output.text_content}'''")
        print(f"Sections Identified: {norm_doc_output.sections}")
        print(f"Metadata: {norm_doc_output.metadata}")

    print("\nNormalization module test finished.")
