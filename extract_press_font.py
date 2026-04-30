import zipfile, os
zip_path = os.path.join(os.path.dirname(__file__), 'Press_Start_2P.zip')
out_dir = os.path.join(os.path.dirname(__file__), 'assets', 'fonts')
os.makedirs(out_dir, exist_ok=True)
if os.path.exists(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.lower().endswith('.ttf') or name.lower().endswith('.otf'):
                z.extract(name, out_dir)
                print('Extracted', name, 'to', out_dir)
else:
    print('Zip not found:', zip_path)
