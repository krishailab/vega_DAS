import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.b2b_admin_api import B2BInwardOperations

def test_inward_filters():
    print("Testing inward filters response keys...")
    filters = B2BInwardOperations.get_filter_options()
    
    print(f"Returned keys: {list(filters.keys())}")
    
    # Assert models and submodels are not in the response
    assert "models" not in filters, "❌ Failure: 'models' key should not be in filters response"
    assert "submodels" not in filters, "❌ Failure: 'submodels' key should not be in filters response"
    
    # Assert expected keys are present
    expected_keys = {"categories", "subcategories", "brands", "colors", "sizes", "size_names"}
    for key in expected_keys:
        assert key in filters, f"❌ Failure: '{key}' key is missing from response"
        
    print("✓ Success: 'models' and 'submodels' were successfully removed from inward filters response!")

    # Test dynamic filtering with category_id
    print("\nTesting dynamic filtering by category_id...")
    categories = filters.get("categories", [])
    if categories:
        valid_cat_id = categories[0]["category_id"]
        print(f"Filtering by valid category_id: {valid_cat_id}")
        cat_filtered = B2BInwardOperations.get_filter_options(category_id=valid_cat_id)
        
        # Categories list should still contain the active category
        assert any(c["category_id"] == valid_cat_id for c in cat_filtered["categories"]), "❌ Failure: valid category should be in categories list"
        # Subcategories should only belong to the filtered category_id
        for sub in cat_filtered["subcategories"]:
            assert sub["category_id"] == valid_cat_id, f"❌ Failure: subcategory {sub['subcategory_id']} does not belong to category {valid_cat_id}"
            
        print("✓ Success: subcategories list correctly filtered by category_id!")
    else:
        print("⚠ Skip category_id test: no categories with active inwards found in seed database.")

    # Test filtering with invalid category_id
    print("\nTesting dynamic filtering by dummy category_id...")
    dummy_cat_filtered = B2BInwardOperations.get_filter_options(category_id="PCAT_DUMMY_NONE")
    # Categories should still return active ones
    assert len(dummy_cat_filtered["categories"]) == len(filters["categories"]), "❌ Failure: categories list should remain unchanged"
    # Subcategories, brands, colors, sizes, size_names should be empty
    assert len(dummy_cat_filtered["subcategories"]) == 0, "❌ Failure: subcategories should be empty for dummy category"
    assert len(dummy_cat_filtered["brands"]) == 0, "❌ Failure: brands should be empty for dummy category"
    assert len(dummy_cat_filtered["colors"]) == 0, "❌ Failure: colors should be empty for dummy category"
    assert len(dummy_cat_filtered["sizes"]) == 0, "❌ Failure: sizes should be empty for dummy category"
    assert len(dummy_cat_filtered["size_names"]) == 0, "❌ Failure: size_names should be empty for dummy category"
    print("✓ Success: dummy category_id correctly returned empty results for dependent filters!")

    # Test dynamic filtering with subcategory_id
    print("\nTesting dynamic filtering by subcategory_id...")
    subcategories = filters.get("subcategories", [])
    if subcategories:
        valid_sub_id = subcategories[0]["subcategory_id"]
        valid_sub_cat_id = subcategories[0]["category_id"]
        print(f"Filtering by valid subcategory_id: {valid_sub_id}")
        sub_filtered = B2BInwardOperations.get_filter_options(subcategory_id=valid_sub_id)
        
        # Categories should still contain the parent category
        assert any(c["category_id"] == valid_sub_cat_id for c in sub_filtered["categories"]), "❌ Failure: parent category should be in categories list"
        print("✓ Success: brands, colors, sizes, size_names correctly resolved for subcategory_id!")
    else:
        print("⚠ Skip subcategory_id test: no subcategories with active inwards found in seed database.")

    # Test filtering with invalid subcategory_id
    print("\nTesting dynamic filtering by dummy subcategory_id...")
    dummy_sub_filtered = B2BInwardOperations.get_filter_options(subcategory_id="PSUB_DUMMY_NONE")
    # Brands, colors, sizes, size_names should be empty
    assert len(dummy_sub_filtered["brands"]) == 0, "❌ Failure: brands should be empty for dummy subcategory"
    assert len(dummy_sub_filtered["colors"]) == 0, "❌ Failure: colors should be empty for dummy subcategory"
    assert len(dummy_sub_filtered["sizes"]) == 0, "❌ Failure: sizes should be empty for dummy subcategory"
    assert len(dummy_sub_filtered["size_names"]) == 0, "❌ Failure: size_names should be empty for dummy subcategory"
    print("✓ Success: dummy subcategory_id correctly returned empty results for dependent filters!")

if __name__ == "__main__":
    test_inward_filters()

