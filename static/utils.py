def abilita_assi_chart(xlsx_path):
    import zipfile
    import shutil
    import os
    import tempfile
    from lxml import etree

    temp_dir = tempfile.mkdtemp()

    try:
        with zipfile.ZipFile(xlsx_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        chart_dir = os.path.join(temp_dir, 'xl', 'charts')
        ns = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart'}

        for chart_file in os.listdir(chart_dir):
            chart_path = os.path.join(chart_dir, chart_file)
            tree = etree.parse(chart_path)
            root = tree.getroot()

            # Abilita asse X (c:catAx)
            for cat_ax in root.findall('.//c:catAx', namespaces=ns):
                delete_tag = cat_ax.find('c:delete', namespaces=ns)
                if delete_tag is None:
                    delete_tag = etree.SubElement(cat_ax, '{%s}delete' % ns['c'])
                delete_tag.text = '0'

            # Abilita asse Y (c:valAx)
            for val_ax in root.findall('.//c:valAx', namespaces=ns):
                delete_tag = val_ax.find('c:delete', namespaces=ns)
                if delete_tag is None:
                    delete_tag = etree.SubElement(val_ax, '{%s}delete' % ns['c'])
                delete_tag.text = '0'

            tree.write(chart_path)

        new_xlsx_path = xlsx_path.replace(".xlsx", "_patched.xlsx")
        with zipfile.ZipFile(new_xlsx_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for foldername, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    abs_path = os.path.join(foldername, filename)
                    rel_path = os.path.relpath(abs_path, temp_dir)
                    zip_out.write(abs_path, rel_path)

        return new_xlsx_path

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
