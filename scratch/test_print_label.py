import os
import sys
from datetime import datetime
from app.database import (
    users_collection, product_variants_collection,
    product_submodels_collection, product_models_collection,
    job_cards_collection, qr_master_collection, parts_collection
)
from app.api.job_card_api import JobCardOperations
from app import schemas

async def run_test():
    print("Initializing print-labels mock setup...")
    
    # 1. Clean previous seeds if any
    users_collection.delete_many({"user_id": "mock_master_admin_01"})
    product_variants_collection.delete_many({"variant_id": "PVAR_TEST_LABEL_01"})
    product_submodels_collection.delete_many({"submodel_id": "PSMD_TEST_LABEL_01"})
    product_models_collection.delete_many({"model_id": "PMD_TEST_LABEL_01"})
    parts_collection.delete_many({"part_id": "PRT_TEST_LABEL_01"})
    
    # 2. Seed mock Master Admin
    mock_user = {
        "user_id": "mock_master_admin_01",
        "first_name": "Label",
        "last_name": "Tester",
        "role": "Master Admin",
        "department": "Production",
        "part_id": "PRT_TEST_LABEL_01",
        "plant_id": "PLT26AA0001"
    }
    users_collection.insert_one(mock_user)
    
    # 3. Seed mock Part
    mock_part = {
        "part_id": "PRT_TEST_LABEL_01",
        "name": "Full Face Shell",
        "composition": "ABS Shell"
    }
    parts_collection.insert_one(mock_part)
    
    # 4. Seed mock model hierarchy
    mock_model = {
        "model_id": "PMD_TEST_LABEL_01",
        "name": "APEX TEST"
    }
    product_models_collection.insert_one(mock_model)
    
    mock_submodel = {
        "submodel_id": "PSMD_TEST_LABEL_01",
        "model_id": "PMD_TEST_LABEL_01",
        "name": "APEX PREMIUM GLASS"
    }
    product_submodels_collection.insert_one(mock_submodel)
    
    mock_variant = {
        "variant_id": "PVAR_TEST_LABEL_01",
        "sku_no": "TEST-APX-GLASS-WMB-L",
        "submodel_id": "PSMD_TEST_LABEL_01",
        "color": "Neon Green Blue",
        "size": 60,
        "size_name": "Large (600 mm)",
        "mrp": 5499.0,
        "finish": "Glossy",
        "certification": ["DOT", "ISI", "ECE"],
        "gs1_barcode": "8901234567890",
        "carton_box_size": 4,
        "carton_barcode": "8901234567890-C"
    }
    product_variants_collection.insert_one(mock_variant)
    
    # 5. Create Assemble Job Card (Quantity = 3)
    print("Creating assemble job card...")
    jc_create = schemas.JobCardCreate(
        jobcard_no="JBC-PRINT-TEST-001",
        jobcard_date="22/11/2026",
        part_composition="Axor Apex Helmet Structure",
        quantity=3
    )
    
    jc_doc = JobCardOperations.create_assemble_job_card(
        job_card=jc_create,
        variant_sku="TEST-APX-GLASS-WMB-L",
        current_user=mock_user
    )
    jobcard_id = jc_doc["jobcard_id"]
    print(f"✓ Job card created successfully: {jobcard_id}")
    
    # 6. Generate printable labels PDF (Full Batch)
    print("Generating printable labels PDF (Full Batch)...")
    response = JobCardOperations.print_labels(jobcard_id=jobcard_id, current_user=mock_user)
    
    # Write response bytes to disk
    pdf_path = "scratch/jobcard_labels_output.pdf"
    pdf_bytes = b"".join([chunk async for chunk in response.body_iterator]) if hasattr(response, "body_iterator") else response.body
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"✓ PDF saved to: {pdf_path}")
    assert os.path.exists(pdf_path), "PDF file was not created!"
    file_size = os.path.getsize(pdf_path)
    assert file_size > 1000, f"PDF file is too small! Size: {file_size} bytes"
    print(f"✓ PDF validation passed. Size: {file_size} bytes")

    # Test Range Sequence: start_index=2, limit=2
    print("Testing sequence parameter: start_index=2, limit=2...")
    seq_response = JobCardOperations.print_labels(jobcard_id=jobcard_id, current_user=mock_user, start_index=2, limit=2)
    seq_pdf_bytes = b"".join([chunk async for chunk in seq_response.body_iterator]) if hasattr(seq_response, "body_iterator") else seq_response.body
    seq_path = "scratch/jobcard_labels_seq_2_3.pdf"
    with open(seq_path, "wb") as f:
        f.write(seq_pdf_bytes)
    assert os.path.exists(seq_path) and os.path.getsize(seq_path) > 1000, "Sequence PDF failed generation"
    print(f"✓ Sequence PDF successfully generated at {seq_path} (size: {os.path.getsize(seq_path)} bytes)")

    # Test One-by-one: start_index=1, limit=1
    print("Testing one-by-one parameter: start_index=1, limit=1...")
    one_response = JobCardOperations.print_labels(jobcard_id=jobcard_id, current_user=mock_user, start_index=1, limit=1)
    one_pdf_bytes = b"".join([chunk async for chunk in one_response.body_iterator]) if hasattr(one_response, "body_iterator") else one_response.body
    one_path = "scratch/jobcard_labels_one_by_one.pdf"
    with open(one_path, "wb") as f:
        f.write(one_pdf_bytes)
    assert os.path.exists(one_path) and os.path.getsize(one_path) > 1000, "One-by-one PDF failed generation"
    print(f"✓ One-by-one PDF successfully generated at {one_path} (size: {os.path.getsize(one_path)} bytes)")

    # Fetch a seeded QR ID to test specific QR lookup
    seeded_qr = qr_master_collection.find_one({"jobcard_id": jobcard_id})
    if seeded_qr:
        specific_qr_id = seeded_qr["qr_id"]
        print(f"Testing specific QR ID printing: {specific_qr_id}...")
        spec_response = JobCardOperations.print_labels(jobcard_id=jobcard_id, current_user=mock_user, qr_id=specific_qr_id)
        spec_pdf_bytes = b"".join([chunk async for chunk in spec_response.body_iterator]) if hasattr(spec_response, "body_iterator") else spec_response.body
        spec_path = f"scratch/jobcard_labels_spec_{specific_qr_id}.pdf"
        with open(spec_path, "wb") as f:
            f.write(spec_pdf_bytes)
        assert os.path.exists(spec_path) and os.path.getsize(spec_path) > 1000, "Specific QR ID PDF failed generation"
        print(f"✓ Specific QR ID PDF successfully generated at {spec_path} (size: {os.path.getsize(spec_path)} bytes)")
    
    # Clean up test output files
    for path in [pdf_path, seq_path, one_path, f"scratch/jobcard_labels_spec_{seeded_qr['qr_id']}.pdf" if seeded_qr else ""]:
        if path and os.path.exists(path):
            os.remove(path)
    
    # Clean up test documents
    users_collection.delete_many({"user_id": "mock_master_admin_01"})
    product_variants_collection.delete_many({"variant_id": "PVAR_TEST_LABEL_01"})
    product_submodels_collection.delete_many({"submodel_id": "PSMD_TEST_LABEL_01"})
    product_models_collection.delete_many({"model_id": "PMD_TEST_LABEL_01"})
    parts_collection.delete_many({"part_id": "PRT_TEST_LABEL_01"})
    job_cards_collection.delete_many({"jobcard_id": jobcard_id})
    qr_master_collection.delete_many({"jobcard_id": jobcard_id})
    
    print("\n✓ ALL PRINT-LABEL INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    # Support running the async body iterator test in synchronous runner
    import asyncio
    
    async def main():
        await run_test()
        
    # Standard python async execution wrapper
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If run within another event loop
        import nest_asyncio
        nest_asyncio.apply()
        
    loop.run_until_complete(main())
