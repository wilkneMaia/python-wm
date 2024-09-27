import os
import camelot
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

print(matplotlib.get_backend())

file_name = "09_24"
path = os.path.abspath(f"src/pdf-extractor/files/pdf/coelce/{file_name}.pdf")

tables = camelot.read_pdf(
    path,
    pages="1",
    flavor="stream",
    table_areas=["41,533,346,304"],
    columns=["130, 150, 170, 203, 226, 253, 278, 300, 320"],
    strip_text=".\n",
    password="97413",
)
print(tables[0].parsing_report)

camelot.plot(tables[0], kind="contour")
plt.show()

# Obtenha o DataFrame da primeira tabela
# df = tables[0].df

# # Exiba o DataFrame original
# print("DataFrame original:")
# print(df)

# # Encontre a linha onde aparece "TOTAL"
# total_index = df[df.apply(lambda row: row.astype(str).str.contains('TOTAL', case=False).any(), axis=1)].index

# # Se a linha "TOTAL" for encontrada, corte o DataFrame até essa linha
# if not total_index.empty:
#     total_index = total_index[0]
#     df_filtered = df.loc[:total_index]
# else:
#     df_filtered = df

# # Exiba o DataFrame filtrado
# print("DataFrame filtrado:")
# print(df_filtered)

# # Opcional: Salve o DataFrame filtrado em um arquivo CSV
# # df_filtered.to_csv('filtered_table.csv', index=False)

# print("Pausing...")
