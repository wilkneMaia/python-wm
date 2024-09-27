import os
from typing import Optional
import camelot
import logging
import pandas as pd
from configs.rules.notes import rules_dict

logging.basicConfig(level=logging.INFO)

class PDFExtractor:
    def __init__(self, file_name: str, configs: dict):
        self.file_name = file_name
        self.path = os.path.abspath(f"src/pdf-extractor/files/pdf/{configs['name'].lower()}/{file_name}.pdf")
        self.csv_path = os.path.abspath(f"src/pdf-extractor/files/csv/")
        self.configs = configs

    def start(self) -> None:
        """
        Inicia o processo de extração do PDF e salva como CSV.
        """
        logging.info(f"Iniciando processamento do PDF - {self.file_name}")
        table = self.get_table_data(self.configs["table_areas"], self.configs["columns"])

        if table is not None:
            logging.info("Tabela extraída:")
            logging.info(table.head())  # Visualização inicial dos dados
            self.save_csv(table, self.file_name)
        else:
            logging.error(f"Erro ao processar o arquivo {self.file_name}. Nenhuma tabela foi encontrada.")

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

    def save_csv(self, df: pd.DataFrame, file_name: str) -> None:
        """
        Salva o DataFrame em um arquivo CSV.
        """
        if not os.path.exists(self.csv_path):
            os.makedirs(self.csv_path, exist_ok=True)
        path = os.path.join(self.csv_path, f"{file_name}.csv")
        df.to_csv(path, sep=";", index=False)

if __name__ == "__main__":
    company_name = 'coelce'
    path = os.path.abspath(f"src/pdf-extractor/files/pdf/{company_name}")
    files = os.listdir(path)

    for file in files:
        if file.endswith(".pdf"):
            extractor = PDFExtractor(file.split('.')[0], configs=rules_dict[company_name])
            extractor.start()

    logging.info("Todos os arquivos foram processados")
