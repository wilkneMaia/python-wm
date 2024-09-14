import os
import camelot
import pandas as pd
import logging
from unidecode import unidecode
from configs.rules.notes import rules_dict

logging.basicConfig(level=logging.INFO)

class PDFExtractor:
    def __init__(self, file_name, configs):
        self.file_name = file_name
        self.path = os.path.abspath(f"src/pdf-extractor/files/pdf/{configs['name'].lower()}/{file_name}.pdf")
        self.csv_path = os.path.abspath(f"src/pdf-extractor/files/csv/")
        self.configs = configs

    def start(self):
        logging.info(f"Start pdf - {self.file_name}")
        header = self.get_table_data(self.configs["table_areas"], self.configs["columns"], self.configs["fix"])

        if header is not None:
            # Exibir DataFrame para verificação
            print("DataFrame Original:")
            print(header.head(50))  # Ou use qualquer método de visualização
            print("======")

            # Corrigir o cabeçalho do DataFrame
            corrected_df = self.clean_and_correct_header(header)

            # Filtrar o DataFrame até a linha com "Subtotal Faturamento"
            filtered_df = self.filter_until_subtotal(corrected_df)

            # Exibir DataFrame após filtro
            print("DataFrame Filtrado:")
            print(filtered_df.head(20))  # Ou use qualquer método de visualização

            # Aqui chamamos a função que vai calcular o Percentual da CIP e printar os valores
            filtered_df = self.calculate_cip_percentage(filtered_df)

            logging.info(f"Saving csv - {self.file_name}")
            self.save_csv(filtered_df, self.file_name)
        else:
            logging.error(f"Erro ao processar o arquivo {self.file_name}. Nenhuma tabela foi encontrada.")

    def get_table_data(self, table_areas, table_columns, fix=True):
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
            # Pegue a primeira tabela como exemplo
            return tables[0].df
        else:
            logging.warning(f"Nenhuma tabela encontrada no arquivo {self.file_name}.")
            return None

    def save_csv(self, df, file_name):
        if not os.path.exists(self.csv_path):
            os.makedirs(self.csv_path, exist_ok=True)
        path = os.path.join(self.csv_path, f"{file_name}.csv")
        df.to_csv(path, sep=";", index=False)

    def add_infos(self, header, content):
        infos = header.iloc[0]
        df = pd.DataFrame([infos.values] * len(content), columns=header.columns)
        content = pd.concat([content.reset_index(drop=True), df.reset_index(drop=True)], axis=1)
        content["Data de Inserção"] = pd.Timestamp('today').normalize()
        return content

    @staticmethod
    def fix_header(df):
        df.columns = df.iloc[0]
        df = df.drop(0)
        df = df.drop(df.columns[0], axis=1)
        return df

    def sanitize_column_names(self, df):
        # Verifique o tipo de dados de cada coluna
        df.columns = [unidecode(str(col)) if isinstance(col, str) else col for col in df.columns]

        # Certifique-se de que df.columns são strings antes de aplicar métodos .str
        df.columns = df.columns.astype(str)
        df.columns = df.columns.str.replace(' ', '_')
        df.columns = df.columns.str.replace(r'\W', '', regex=True)
        df.columns = df.columns.str.lower()
        return df

    def filter_until_subtotal(self, df):
        """
        Filtra o DataFrame até a linha que contém o texto 'Subtotal Faturamento'.

        Args:
            df (pd.DataFrame): O DataFrame a ser filtrado.

        Returns:
            pd.DataFrame: O DataFrame filtrado até a linha antes de 'Subtotal Faturamento'.
        """
        # Encontrar a linha onde aparece "Subtotal Faturamento"
        subtotal_index = df[df.apply(lambda row: row.astype(str).str.contains('Subtotal Faturamento', case=False).any(), axis=1)].index

        # Se a linha "Subtotal Faturamento" for encontrada, corte o DataFrame até a linha anterior
        if not subtotal_index.empty:
            subtotal_index = subtotal_index[0]
            df_filtered = df.loc[:subtotal_index-1]
        else:
            df_filtered = df

        return df_filtered

    def clean_and_correct_header(self, df):
        """
        Limpa o DataFrame removendo linhas não necessárias e define o cabeçalho correto.

        Args:
            df (pd.DataFrame): O DataFrame a ser limpo e corrigido.

        Returns:
            pd.DataFrame: O DataFrame limpo e com o cabeçalho corrigido.
        """
        # Remover linhas com cabeçalhos repetidos ou não desejados
        df = df.dropna(how="all")  # Remove linhas onde todos os valores são NaN

        # Defina o cabeçalho esperado (primeira linha válida após a limpeza)
        expected_header = [
            "Itens_de_Fatura", "Unid", "Quant", "Preço_unit_(R$)_com_tributos", "Valor_(R$)",
            "PIS/COFINS", "Base_Calc_ICMS_(R$)", "Alíquota_ICMS", "ICMS", "Tarifa_unit_(R$)"
        ]

        # Encontre a primeira linha válida para ser o cabeçalho
        df = df.reset_index(drop=True)
        first_valid_index = df.index[df.notnull().all(axis=1)][0]  # Primeiro índice onde não há NaN
        df.columns = df.iloc[first_valid_index]
        df = df.drop(range(first_valid_index + 1))  # Remove linhas acima do novo cabeçalho

        # Reconfigurar o cabeçalho para o formato esperado
        df.columns = expected_header

        # Remover linhas adicionais que contêm valores indesejados
        # Verifica se as linhas contêm informações adicionais que não pertencem aos dados
        df = df[~df.apply(lambda row: row.astype(str).str.contains(';;;|com tributos|ICMS', case=False).any(), axis=1)]
        df = df.reset_index(drop=True)

        return df


    def tratar_valores_monetarios(self, df, coluna):
        """
        Função para tratar valores monetários na coluna especificada.
        Converte valores para numérico, tratando vírgulas como separador decimal
        e valores negativos que possuem o símbolo '-'.
        """
        # Remover espaços em branco e garantir que é uma string antes de manipular
        df.loc[:, coluna] = df[coluna].astype(str).str.strip()

        # Verificar se o valor é negativo (se contém '-'),
        # e converter corretamente vírgulas para separador decimal sem substituí-las
        df.loc[:, coluna] = df[coluna].apply(
            lambda x: -pd.to_numeric(x.replace('-', '').replace(',', '.'), errors='coerce') if '-' in x
            else pd.to_numeric(x.replace(',', '.'), errors='coerce')
        )

        return df


    def calculate_cip_percentage(self, df):
        """
        Função para printar os valores da linha "Energia Ativa Fornecida TE", "Energia Ativa Fornecida TUSD"
        e "CIP ILUM PUB PREF MUNICIPAL" com a coluna "Valor_(R$)", calcular a somatória dos dois primeiros valores
        e calcular o percentual de CIP ILUM PUB PREF MUNICIPAL sobre a soma de TE e TUSD.
        """

        # Tratar a coluna 'Valor_(R$)' antes de fazer a soma
        df = self.tratar_valores_monetarios(df, 'Valor_(R$)')

        # Filtrar as linhas que contenham "Energia Ativa Fornecida TE" na coluna 'Itens_de_Fatura'
        energia_ativa_te = df[df['Itens_de_Fatura'].str.contains('Energia Ativa Fornecida TE', case=False)]

        if not energia_ativa_te.empty:
            # Printar os valores da coluna "Valor_(R$)" para "Energia Ativa Fornecida TE"
            print("Valores da linha 'Energia Ativa Fornecida TE' na coluna 'Valor_(R$)':")
            print(energia_ativa_te['Valor_(R$)'])
            valor_te = energia_ativa_te['Valor_(R$)'].sum()
        else:
            print("Linha 'Energia Ativa Fornecida TE' não encontrada.")
            valor_te = 0

        # Filtrar as linhas que contenham "Energia Ativa Fornecida TUSD" na coluna 'Itens_de_Fatura'
        energia_ativa_tusd = df[df['Itens_de_Fatura'].str.contains('Energia Ativa Fornecida TUSD', case=False)]

        if not energia_ativa_tusd.empty:
            # Printar os valores da coluna "Valor_(R$)" para "Energia Ativa Fornecida TUSD"
            print("Valores da linha 'Energia Ativa Fornecida TUSD' na coluna 'Valor_(R$)':")
            print(energia_ativa_tusd['Valor_(R$)'])
            valor_tusd = energia_ativa_tusd['Valor_(R$)'].sum()
        else:
            print("Linha 'Energia Ativa Fornecida TUSD' não encontrada.")
            valor_tusd = 0

        # Somar os dois valores
        valor_total = valor_te + valor_tusd
        print(f"Somatória dos valores TE e TUSD: {valor_total}")

        # Filtrar as linhas que contenham "CIP ILUM PUB PREF MUNICIPAL" na coluna 'Itens_de_Fatura'
        cip_ilum = df[df['Itens_de_Fatura'].str.contains('CIP ILUM PUB PREF MUNICIPAL', case=False)]

        if not cip_ilum.empty:
            # Printar os valores da coluna "Valor_(R$)" para "CIP ILUM PUB PREF MUNICIPAL"
            print("Valores da linha 'CIP ILUM PUB PREF MUNICIPAL' na coluna 'Valor_(R$)':")
            print(cip_ilum['Valor_(R$)'])
            valor_cip = cip_ilum['Valor_(R$)'].sum()
        else:
            print("Linha 'CIP ILUM PUB PREF MUNICIPAL' não encontrada.")
            valor_cip = 0

        # Calcular o percentual de CIP ILUM PUB PREF MUNICIPAL sobre a soma de TE e TUSD
        if valor_total > 0:
            percentual_cip = (valor_cip / valor_total) * 100
            print(f"Percentual de CIP ILUM PUB PREF MUNICIPAL sobre TE e TUSD: {percentual_cip:.2f}%")
        else:
            print("Somatória de TE e TUSD é zero. Não foi possível calcular o percentual.")
            percentual_cip = 0

        # Criar a coluna 'percentual_cip' no DataFrame e preencher o valor apenas na linha de CIP
        df['percentual_cip'] = None  # Cria a coluna com valores vazios inicialmente
        df.loc[df['Itens_de_Fatura'].str.contains('CIP ILUM PUB PREF MUNICIPAL', case=False), 'percentual_cip'] = percentual_cip

        return df



def list_files(folder):
    try:
        files = [os.path.splitext(f)[0] for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        return files
    except FileNotFoundError:
        logging.info(f"A pasta '{folder}' não foi encontrada.")
        return []
    except Exception as e:
        logging.info(f"Ocorreu um erro: {e}")
        return []

if __name__ == "__main__":
    company_name = 'coelce'
    path = os.path.abspath(f"src/pdf-extractor/files/pdf/{company_name}")
    files = list_files(path)

    for file in files:
        extractor = PDFExtractor(file, configs=rules_dict[company_name])
        extractor.start()

    logging.info("Todos os arquivos foram processados")
