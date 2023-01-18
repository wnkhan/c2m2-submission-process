python prepare_C2M2_submission.py

if [[ ! -e "frictionless_validation" ]]; then
    mkdir frictionless_validation
else
    echo "frictionless_validation already exists."
fi

cp autogenerated_C2M2_term_tables/*.tsv  frictionless_validation
cp draft_C2M2_submission_TSVs/*.tsv      frictionless_validation

mv C2M2_datapackage.json                 frictionless_validation