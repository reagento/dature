dature validate \
    --schema myschema:Settings \
    --source 'type=dature.JsonSource,file=sources/defaults.json' \
    --source 'type=dature.JsonSource,file=sources/overrides.json' \
    --strategy last_wins
