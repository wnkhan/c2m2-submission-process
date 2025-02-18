import pandas as pd
import os

from table_ops import TableJoiner, is_column_present
from file_locations import file_locations


foreign_key_mappings = {
    'portal_studies': {
        'study': {'left': 'studies_on_portal', 'right': 'SD_kf_id'},
        'participant': {'left': 'studies_on_portal', 'right': 'PT_study_id'}
    },
    'participant': {
        'biospecimen': {'left': 'PT_kf_id', 'right': 'BS_participant_id'},
        'project_disease': {'left': 'PT_study_id', 'right': 'study_id'}
    },
    'biospecimen': {
        'project_disease': {'left': 'PT_study_id', 'right': 'study_id'},
        'biospecimen_genomic_file': {'left': 'BS_kf_id', 'right': 'BG_biospecimen_id'}
    },
    'biospecimen_genomic_file': {
        'genomic_files': {'left': 'BG_genomic_file_id', 'right': 'GF_kf_id'},
        'sequencing_experiment_genomic_file': {'left': '', 'right': ''}
    },
    'genomic_files': {
        'sequencing_experiment_genomic_file': {'left':'GF_kf_id', 'right':'SG_genomic_file_id'}
    },
    'sequencing_experiment_genomic_file': {
        'sequencing_experiment': {'left': 'SG_sequencing_experiment_id', 'right': 'SE_kf_id'}
    }
}

kf_tablenames = ['study','participant','biospecimen','biospecimen_genomic_file',
                # TODO: Using genomic_files is a hack. Find better solution later.
                 'genomic_files','sequencing_experiment_genomic_file','sequencing_experiment']

kf_tables_with_visibility = ['participant','biospecimen','biospecimen_genomic_file',
                             'genomic_files','sequencing_experiment_genomic_file','sequencing_experiment']

# Required due to ingest using endpoint names when ingesting tables
table_to_endpoint_name = {
    'study': 'studies',
    'participant': 'participants',
    'biospecimen': 'biospecimens',
    'biospecimen_genomic_file': 'biospecimen-genomic-files',
    'genomic_files': 'genomic-files',
    'sequencing_experiment_genomic_file': 'sequencing-experiment-genomic-files',
    'sequencing_experiment': 'sequencing-experiments'
}

class KfTableCombiner:
    """
    A class for combining tables from the Kids First platform.

    Attributes:
        df_dict (dict): A dictionary containing data frames for several tables.
        table_list (list): A list of tables to be joined.

    Methods:
        get_keys: Returns the keys to be used in joining two tables.
        get_combined_table: Returns a data frame containing the combined table.
    """
    df_dict = {}
    df_dict.setdefault('portal_studies',pd.read_table(os.path.join(file_locations.get_etl_path(),'studies_on_portal.tsv')))

    def __init__(self, tables_to_join: list):
        """
        Initializes the KfTableCombiner object.

        Args:
            tables_to_join (list): A list of tables to be joined.
        """
        self.table_list = tables_to_join
        self.add_tables_to_df_dict()

    def add_tables_to_df_dict(self):
        """
        Dynamically adds tables to the `df_dict` dictionary.
        """
        for table_name in self.table_list:
            if table_name not in KfTableCombiner.df_dict:
                file_path = os.path.join(file_locations.get_ingested_path(),f'{table_to_endpoint_name[table_name]}.csv')

                if table_name in kf_tablenames:
                    table_df = pd.read_csv(file_path, low_memory=False)

                    if table_name == "genomic_files":
                        # Parquet files are visible in DS but not intended to be on the portal,
                        # so they are omitted from the table here
                        table_df = table_df[(table_df['visible']) & (table_df['file_format'] != "parquet")] 

                    elif table_name in kf_tables_with_visibility and is_column_present(file_path, 'visible'):
                        table_df = table_df[table_df['visible'] == True]

                    KfTableCombiner.df_dict[table_name] = table_df

    def get_combined_table(self) -> pd.DataFrame:
        """
        Returns a data frame containing the combined table.

        Returns:
            A data frame containing the combined table.
        """
        base_df_name = self.table_list[0]
        base_df = KfTableCombiner.df_dict[base_df_name] 

        for table_name in self.table_list[1:]:
            left, right = foreign_key_mappings[base_df_name][table_name].values() 
            base_df = TableJoiner(base_df) \
                .join_kf_table(KfTableCombiner.df_dict[table_name],
                               left_key=left,
                               right_key=right) \
                .get_result()
            base_df_name = table_name

        base_df = apply_study_parent_child_relationship(base_df) 

        return base_df


def apply_study_parent_child_relationship(the_df: pd.DataFrame):
    child_to_parent = {
        'SD_7YDC1W4H': 'SD_Z6MWD3H0',
        'SD_FYCR78W0': 'SD_Z6MWD3H0',
        'SD_65064P2Z': 'SD_Z6MWD3H0',
        'SD_T8VSYRSG': 'SD_Z6MWD3H0',
        'SD_Y6VRG6MD': 'SD_PREASA7S'
    }

    kf_study_id_cols = ["SD_kf_id","PT_study_id","studies_on_portal"]

    for study_id_col in kf_study_id_cols:
        if (any(study_id_col in col for col in the_df.columns)):
            the_df[study_id_col] = the_df[study_id_col].apply(lambda study_id: child_to_parent.get(study_id, study_id))

    return the_df