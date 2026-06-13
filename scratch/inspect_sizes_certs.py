import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import product_variants_collection, job_cards_collection

print("=== UNIQUE SIZES IN VARIANTS ===")
variants = list(product_variants_collection.find({}))
for v in variants:
    print(f"Variant SKU: {v.get('sku_no')}, size: {v.get('size')} ({type(v.get('size'))}), cert: {v.get('certification')} ({type(v.get('certification'))})")

print("\n=== UNIQUE SIZES IN JOB CARDS ===")
cards = list(job_cards_collection.find({}).limit(10))
for c in cards:
    print(f"JobCard No: {c.get('jobcard_no')}, size: {c.get('size')} ({type(c.get('size'))}), cert: {c.get('certification')} ({type(c.get('certification'))})")
