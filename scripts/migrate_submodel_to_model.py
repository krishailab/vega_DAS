import os
import sys

# Adjust path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import product_models_collection, product_submodels_collection

def migrate_data():
    models = list(product_models_collection.find({}))
    migrated_count = 0
    for model in models:
        model_id = model.get("model_id")
        # Find all submodels for this model
        submodels = list(product_submodels_collection.find({"model_id": model_id}))
        
        if not submodels:
            continue
            
        # We assume all submodels for a given model have the same weight/dimension/certification 
        # or we can just take the first one that has data.
        update_data = {}
        for sm in submodels:
            if "box_weight" in sm and sm["box_weight"] is not None and "box_weight" not in update_data:
                update_data["box_weight"] = sm["box_weight"]
            if "box_dimension" in sm and sm["box_dimension"] is not None and "box_dimension" not in update_data:
                update_data["box_dimension"] = sm["box_dimension"]
            if "carton_weight" in sm and sm["carton_weight"] is not None and "carton_weight" not in update_data:
                update_data["carton_weight"] = sm["carton_weight"]
            if "carton_dimension" in sm and sm["carton_dimension"] is not None and "carton_dimension" not in update_data:
                update_data["carton_dimension"] = sm["carton_dimension"]
            if "certification" in sm and sm["certification"] and "certification" not in update_data:
                update_data["certification"] = sm["certification"]

        if update_data:
            print(f"Updating model {model_id} with data...")
            product_models_collection.update_one({"model_id": model_id}, {"$set": update_data})
            migrated_count += 1
            
    print(f"Migrated fields for {migrated_count} models.")

    # Remove these fields from submodels
    result = product_submodels_collection.update_many(
        {}, 
        {"$unset": {
            "box_weight": "", 
            "box_dimension": "", 
            "carton_weight": "", 
            "carton_dimension": "", 
            "certification": ""
        }}
    )
    print(f"Unset fields in {result.modified_count} submodels.")

if __name__ == "__main__":
    migrate_data()
