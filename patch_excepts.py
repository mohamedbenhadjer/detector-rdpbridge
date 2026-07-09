import sys

with open('sitecustomize.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip_next = 0
for i, line in enumerate(lines):
    if skip_next > 0:
        skip_next -= 1
        continue
    
    # In _get_support_context, lines ~908-923
    if 'try:' in line and 'if page_obj and hasattr(page_obj, "context"):' in lines[i+1]:
        # remove try:
        pass
    elif 'except Exception:' in line and 'pass' in lines[i+1] and 'if page_obj and hasattr(page_obj, "context"):' in lines[i-14]:
        # wait, let's just do text replacement
        pass

