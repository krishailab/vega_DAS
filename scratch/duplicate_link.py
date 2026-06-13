import re

with open("app/api/scan_api.py", "r") as f:
    content = f.read() 
match = re.search(r'@router\.post\("/link".*?def link_parts.*?return assembly_doc\n', content, re.DOTALL)
if not match:
    print("Could not find link_parts")
    exit(1)

link_code = match.group(0)
dispatch_code = link_code.replace('@router.post("/link"', '@router.post("/dispatch"')
dispatch_code = dispatch_code.replace('def link_parts(', 'def dispatch_parts(')

validation_code = """
    if not station.get("is_dispatch"):
        raise HTTPException(status_code=400, detail="This station is not configured for dispatch")
"""

station_check = """    if not station:
        raise HTTPException(status_code=400, detail="Assigned station not found")"""

dispatch_code = dispatch_code.replace(station_check, station_check + validation_code)

# Insert the dispatch_code after link_parts
new_content = content.replace(link_code, link_code + "\n" + dispatch_code)

with open("app/api/scan_api.py", "w") as f:
    f.write(new_content)

print("Successfully duplicated link_parts to dispatch_parts")
