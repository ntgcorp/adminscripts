import os
import html

def _apply_tags(value, tags_str):
    """Applica i tag al valore in sequenza."""
    if not tags_str:
        return value
    
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    result = value
    
    for tag in tags:
        if tag == "html":
            result = html.escape(str(result))
        elif tag == "trim.lr":
            result = str(result).strip()
        elif tag == "lcase":
            result = str(result).lower()
        elif tag == "ucase":
            result = str(result).upper()
        elif tag == "null.str":
            if result is None or result == "":
                result = ""
        elif tag == "null.zero":
            if result is None or result == "":
                result = "0"
        elif tag.startswith("len.space."):
            try:
                max_len = int(tag.split(".")[2])
                s = str(result)
                if len(s) < max_len:
                    s = s + " " * (max_len - len(s))
                else:
                    s = s[:max_len]
                result = s
            except (ValueError, IndexError):
                pass
        elif tag.startswith("len."):
            try:
                max_len = int(tag.split(".")[1])
                result = str(result)[:max_len]
            except (ValueError, IndexError):
                pass
        elif tag.startswith("align.left."):
            try:
                width = int(tag.split(".")[2])
                s = str(result)
                if len(s) < width:
                    s = s + " " * (width - len(s))
                else:
                    s = s[:width]
                result = s
            except (ValueError, IndexError):
                pass
        elif tag.startswith("align.right."):
            try:
                width = int(tag.split(".")[2])
                s = str(result)
                if len(s) < width:
                    s = " " * (width - len(s)) + s
                else:
                    s = s[:width]
                result = s
            except (ValueError, IndexError):
                pass
    
    return result

def process_record(template_path, record_data, output_path):
    """
    Elabora un record: legge il template, sostituisce i placeholder con i valori processati.
    
    Args:
        template_path: percorso del file template
        record_data: dict con chiavi 'name', 'value', 'tags'
        output_path: percorso del file di output
    """
    name = record_data.get("name", "")
    value = record_data.get("value", "")
    tags = record_data.get("tags", "")
    
    processed_value = _apply_tags(value, tags)
    
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()
    
    placeholder = f"{{{{{name}}}}}"
    if placeholder in template_content:
        template_content = template_content.replace(placeholder, str(processed_value))
    elif name:
        template_content = template_content.replace(name, str(processed_value))
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template_content)