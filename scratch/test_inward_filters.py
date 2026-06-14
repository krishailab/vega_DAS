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

if __name__ == "__main__":
    test_inward_filters()
