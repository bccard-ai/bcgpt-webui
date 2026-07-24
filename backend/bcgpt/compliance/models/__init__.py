def __getattr__(name):
    _mapping = {
        "AIModelInventory": ".ai_inventory",
        "AIModelInventoryModel": ".ai_inventory",
        "AIModelInventoryForm": ".ai_inventory",
        "AIModelInventoryTable": ".ai_inventory",
        "AIModelInventories": ".ai_inventory",
        "AIIARecord": ".aiia",
        "AIIARecordModel": ".aiia",
        "AIIARecordForm": ".aiia",
        "AIIARecordTable": ".aiia",
        "AIIARecords": ".aiia",
        "AIIncident": ".incident",
        "AIIncidentModel": ".incident",
        "AIIncidentForm": ".incident",
        "AIIncidentTable": ".incident",
        "AIIncidents": ".incident",
        "AIFairnessTest": ".fairness_test",
        "AIFairnessTestModel": ".fairness_test",
        "AIFairnessTestForm": ".fairness_test",
        "AIFairnessTestTable": ".fairness_test",
        "AIFairnessTests": ".fairness_test",
        "AIRAGProvenance": ".provenance",
        "AIRAGProvenanceModel": ".provenance",
        "AIRAGProvenanceForm": ".provenance",
        "AIRAGProvenanceTable": ".provenance",
        "AIRAGProvenances": ".provenance",
        "AIVendor": ".vendor",
        "AIVendorModel": ".vendor",
        "AIVendorForm": ".vendor",
        "AIVendorTable": ".vendor",
        "AIVendors": ".vendor",
        "AIDSARRequest": ".dsar",
        "AIDSARRequestModel": ".dsar",
        "AIDSARRequestForm": ".dsar",
        "AIDSARRequestTable": ".dsar",
        "AIDSARRequests": ".dsar",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
