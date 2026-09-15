file = r'F:\invo-system\utility_billing\security\utility_billing_security.xml'

with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# الحل 1: تغيير perm_create من False إلى True
if 'perm_create" eval="False"/>' in content:
    content = content.replace(
        'perm_create" eval="False"/>',
        'perm_create" eval="True"/>'
    )
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS - perm_create changed to True')
else:
    print('NOT FOUND - checking file...')
    idx = content.find('perm_create')
    if idx >= 0:
        print(f'Found perm_create at {idx}:')
        print(repr(content[idx:idx+50]))
    else:
        print('perm_create not found at all')
