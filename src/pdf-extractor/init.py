import os
import camelot
import pandas as pd
import logging
from unidecode import unidecode
from typing import Optional
from configs.rules.notes import rules_dict

logging.basicConfig(level=logging.INFO)

class PDFExtractor:
    def __init__(self, file_name: str, configs: dict):
        self.file_name = file_name
        self.path = os.path.abspath(f"src/pdf-extractor/files/pdf/{configs['name'].lower()}/{file_name}.pdf")
        self.csv_path = os.path.abspath(f"src/pdf-extractor/files/csv/")
        self.configs = configs

    def start(self) -> None:
        logging.info(f"Iniciando processamento do PDF - {self.file_name}")
        header = self.get_table_data(self.configs["table_areas"], self.configs["columns"], self.configs["fix"])

        if header is not None:
            logging.info("DataFrame Original:")
            logging.info(header.head(50))  # Visualização inicial dos dados

            corrected_df = self.clean_and_correct_header(header)

            # Exibir as colunas do DataFrame após a limpeza para diagnóstico
            logging.info(f"Colunas após a correção: {corrected_df.columns.tolist()}")

            # Filtrar o DataFrame até a linha com "Subtotal Faturamento"
            filtered_df = self.filter_until_subtotal(corrected_df)

            logging.info("DataFrame Filtrado:")
            logging.info(filtered_df.head(20))

            # Listar as colunas disponíveis para facilitar o debug
            logging.info(f"Colunas disponíveis: {filtered_df.columns.tolist()}")

            # Verifique se a coluna "Valor_(R$)" está presente
            if 'Valor_(R$)' not in filtered_df.columns:
                raise KeyError(f"A coluna 'Valor_(R$)' não foi encontrada no DataFrame após a limpeza. Colunas disponíveis: {filtered_df.columns.tolist()}")

            # Chama a função que vai calcular o Percentual da CIP
            filtered_df = self.calculate_cip_percentage(filtered_df)

            # Salva o DataFrame resultante
            logging.info(f"Salvando CSV - {self.file_name}")
            self.save_csv(filtered_df, self.file_name)
        else:
            logging.error(f"Erro ao processar o arquivo {self.file_name}. Nenhuma tabela foi encontrada.")  # <- indented corretamente

    def get_table_data(self, table_areas: str, table_columns: str, fix: bool = True) -> Optional[pd.DataFrame]:
        """
        Extrai dados de uma tabela do PDF usando a biblioteca Camelot.
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
        os.makedirs(self.csv_path, exist_ok=True)
        path = os.path.join(self.csv_path, f"{file_name}.csv")
        df.to_csv(path, sep=";", index=False)

    def clean_and_correct_header(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Limpa o DataFrame removendo linhas não necessárias e define o cabeçalho correto.

        Args:
            df (pd.DataFrame): O DataFrame a ser limpo e corrigido.

        Returns:
            pd.DataFrame: O DataFrame limpo e com o cabeçalho corrigido.
        """
        # Remover linhas vazias ou indesejadas
        df = df.dropna(how="all")  # Remove linhas onde todos os valores são NaN

        # Verificar se há cabeçalhos duplicados, linhas extras etc. e definir o cabeçalho real
        df = df.reset_index(drop=True)

        # Tentar encontrar a linha que representa o cabeçalho real
        first_valid_index = df.index[df.notnull().all(axis=1)][0]  # Encontra a primeira linha não-nula
        df.columns = df.iloc[first_valid_index]  # Usa essa linha como cabeçalho
        df = df.drop(range(first_valid_index + 1))  # Remove as linhas acima do cabeçalho

        # Substituir o cabeçalho por um padrão correto se o extraído for inválido
        if 'Valor_(R$)' not in df.columns:
            expected_header = [
                "Itens_de_Fatura", "Unid", "Quant", "Preço_unit_(R$)_com_tributos", "Valor_(R$)",
                "PIS/COFINS", "Base_Calc_ICMS_(R$)", "Alíquota_ICMS", "ICMS", "Tarifa_unit_(R$)"
            ]
            df.columns = expected_header

        # Remover colunas ou linhas indesejadas
        df = df[~df.apply(lambda row: row.astype(str).str.contains(';;;|com tributos|ICMS', case=False).any(), axis=1)]

        df = df.reset_index(drop=True)
        return df

    def filter_until_subtotal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra o DataFrame até a linha que contém 'Subtotal Faturamento'.
        """
        subtotal_index = df[df.apply(lambda row: row.astype(str).str.contains('Subtotal Faturamento', case=False).any(), axis=1)].index
        return df.loc[:subtotal_index[0] - 1] if not subtotal_index.empty else df

    def tratar_valores_monetarios(self, df: pd.DataFrame, coluna: str) -> pd.DataFrame:
        """
        Trata valores monetários.
        """
        # Verifique se a coluna está presente
        if coluna not in df.columns:
            raise KeyError(f"A coluna '{coluna}' não foi encontrada no DataFrame.")

        df[coluna] = df[coluna].astype(str).str.strip()

        def converter_valor(valor: str) -> float:
            valor = valor.strip()
            if valor.endswith('-'):
                return -float(valor.replace('.', '').replace(',', '.').replace('-', ''))
            return float(valor.replace('.', '').replace(',', '.'))

        df[f'{coluna}_convertido'] = df[coluna].apply(converter_valor)
        return df

    def calculate_cip_percentage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula o percentual de CIP ILUM PUB PREF MUNICIPAL sobre a soma de TE e TUSD.
        """
        df = self.tratar_valores_monetarios(df, 'Valor_(R$)')
        coluna_convertida = 'Valor_(R$)_convertido'

        valor_te = df.loc[df['Itens_de_Fatura'].str.contains('Energia Ativa Fornecida TE', case=False), coluna_convertida].sum()
        valor_tusd = df.loc[df['Itens_de_Fatura'].str.contains('Energia Ativa Fornecida TUSD', case=False), coluna_convertida].sum()

        valor_total = valor_te + valor_tusd
        logging.info(f"Somatória dos valores TE e TUSD: {valor_total}")

        valor_cip = df.loc[df['Itens_de_Fatura'].str.contains('CIP ILUM PUB PREF MUNICIPAL', case=False), coluna_convertida].sum()

        percentual_cip = (valor_cip / valor_total) * 100 if valor_total > 0 else 0
        logging.info(f"Percentual de CIP ILUM PUB PREF MUNICIPAL: {percentual_cip:.2f}%")

        df['percentual_cip'] = None
        df.loc[df['Itens_de_Fatura'].str.contains('CIP ILUM PUB PREF MUNICIPAL', case=False), 'percentual_cip'] = percentual_cip

        return df


def list_files(folder: str) -> list:
    """
    Lista os arquivos em um diretório.
    """
    try:
        return [os.path.splitext(f)[0] for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    except FileNotFoundError:
        logging.info(f"A pasta '{folder}' não foi encontrada.")
        return []
    except Exception as e:
        logging.error(f"Ocorreu um erro: {e}")
        return []


if __name__ == "__main__":
    company_name = 'coelce'
    path = os.path.abspath(f"src/pdf-extractor/files/pdf/{company_name}")
    files = list_files(path)

    for file in files:
        extractor = PDFExtractor(file, configs=rules_dict[company_name])
        extractor.start()

    logging.info("Todos os arquivos foram processados")
