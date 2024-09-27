import os
from typing import Optional, List
import camelot
import logging
import pandas as pd
from configs.rules.notes import rules_dict

logging.basicConfig(level=logging.INFO)

class PDFExtractor:
    def __init__(self, file_name: str, configs: dict):
        self.file_name = file_name
        self.path = os.path.abspath(f"src/pdf-extractor/files/pdf/{configs['name'].lower()}/{file_name}.pdf")
        self.configs = configs

    def start(self) -> Optional[pd.DataFrame]:
        """
        Inicia o processo de extração do PDF e retorna o DataFrame.

        Returns:
            pd.DataFrame: Tabela extraída do PDF.
        """
        logging.info(f"Iniciando processamento do PDF - {self.file_name}")

        # Extraindo a tabela principal
        table = self.get_table_data(self.configs["table_areas"], self.configs["columns"])

        # Extraindo a tabela de cabeçalho (header) com MÊS/ANO, VENCIMENTO e TOTAL A PAGAR
        table_header = self.get_table_data(self.configs["table_header"], self.configs["columns_header"])

        if table is not None and table_header is not None:
            logging.info(f"Tabela extraída do arquivo {self.file_name}")
            logging.info(table.head())  # Visualização inicial dos dados da tabela principal

            # Assumindo que `table_header` tenha os valores corretos nas posições esperadas
            mes_ano = table_header.iloc[1, 0]  # Obtém "MÊS/ANO"
            vencimento = table_header.iloc[1, 1]  # Obtém "VENCIMENTO"
            total_a_pagar = table_header.iloc[1, 2]  # Obtém "TOTAL A PAGAR"

            # Adicionando os valores do cabeçalho como colunas no DataFrame principal
            table['MÊS/ANO'] = mes_ano
            table['VENCIMENTO'] = vencimento
            table['TOTAL A PAGAR'] = total_a_pagar

            return table
        else:
            logging.error(f"Erro ao processar o arquivo {self.file_name}. Nenhuma tabela foi encontrada.")
            return None

    def get_table_data(self, table_areas: str, table_columns: str) -> Optional[pd.DataFrame]:
        """
        Extrai dados de uma tabela do PDF usando a biblioteca Camelot.

        Returns:
            pd.DataFrame: Tabela extraída do PDF.
        """
        tables = camelot.read_pdf(
            self.path,
            flavor=self.configs["flavor"],
            table_areas=table_areas,
            columns=table_columns,
            strip_text=self.configs["strip_text"],
            pages=self.configs["pages"],
            password=self.configs["password"],
        )
        if tables.n > 0:
            return tables[0].df
        logging.warning(f"Nenhuma tabela encontrada no arquivo {self.file_name}.")
        return None

if __name__ == "__main__":
    company_name = 'coelce'
    path = os.path.abspath(f"src/pdf-extractor/files/pdf/{company_name}")
    files = os.listdir(path)

    # Lista para armazenar todos os DataFrames
    all_data: List[pd.DataFrame] = []

    for file in files:
        if file.endswith(".pdf"):
            extractor = PDFExtractor(file.split('.')[0], configs=rules_dict[company_name])
            extracted_data = extractor.start()

            # Se a extração foi bem-sucedida, adicionar à lista
            if extracted_data is not None:
                all_data.append(extracted_data)

    # Concatenar todos os DataFrames em um só
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        logging.info("Todos os arquivos foram processados e os dados foram concatenados.")

        # Exibir o DataFrame resultante
        print(combined_data)  # Exibir o DataFrame no terminal

        # Se necessário salvar como CSV ou outro formato
        combined_data.to_csv("src/pdf-extractor/files/combined_data.csv", sep=";", index=False)
    else:
        logging.warning("Nenhuma tabela foi extraída dos PDFs.")
