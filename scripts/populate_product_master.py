#!/usr/bin/env python3
import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from app.utils import generate_custom_id, get_current_time

load_dotenv()

# Raw data to insert
DATA = [
    # --- HALF FACE ---
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE WITH VISOR",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 74.79,
        "skus": {"2XS": "17-000", "XS": "17-001", "S": "17-002", "M": "17-003", "L": "17-004", "XL": "17-005", "2XL": "17-006"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE WITH VISOR",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 74.79,
        "skus": {"2XS": "17-010", "XS": "17-011", "S": "17-012", "M": "17-013", "L": "17-014", "XL": "17-015", "2XL": "17-016"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE NO VISOR",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 74.79,
        "skus": {"2XS": "17-020", "XS": "17-021", "S": "17-022", "M": "17-023", "L": "17-024", "XL": "17-025", "2XL": "17-026"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE NO VISOR",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 74.79,
        "skus": {"2XS": "17-030", "XS": "17-031", "S": "17-032", "M": "17-033", "L": "17-034", "XL": "17-035", "2XL": "17-036"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL",
        "price": 104.49,
        "skus": {"2XS": "17-250", "XS": "17-251", "S": "17-252", "M": "17-253", "L": "17-254", "XL": "17-255", "2XL": "17-256"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE ZIP-OFF WITH VISOR",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-040", "XS": "17-041", "S": "17-042", "M": "17-043", "L": "17-044", "XL": "17-045", "2XL": "17-046"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE ZIP-OFF WITH VISOR",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 80.29,
        "skus": {"2XS": "17-050", "XS": "17-051", "S": "17-052", "M": "17-053", "L": "17-054", "XL": "17-055", "2XL": "17-056"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE INNER SHIELD WITH VISOR",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-300", "XS": "17-301", "S": "17-302", "M": "17-303", "L": "17-304", "XL": "17-305", "2XL": "17-306"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE INNER SHIELD WITH VISOR",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 80.29,
        "skus": {"2XS": "17-310", "XS": "17-311", "S": "17-312", "M": "17-313", "L": "17-314", "XL": "17-315", "2XL": "17-316"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE INNER SHIELD NO VISOR",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-320", "XS": "17-321", "S": "17-322", "M": "17-323", "L": "17-324", "XL": "17-325", "2XL": "17-326"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT BEANIE INNER SHIELD NO VISOR",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 80.29,
        "skus": {"2XS": "17-330", "XS": "17-331", "S": "17-332", "M": "17-333", "L": "17-334", "XL": "17-335", "2XL": "17-336"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE WITH VISOR",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 78.09,
        "skus": {"2XS": "17-700", "XS": "17-701", "S": "17-702", "M": "17-703", "L": "17-704", "XL": "17-705", "2XL": "17-706", "3XL": "17-707"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE WITH VISOR",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 78.09,
        "skus": {"2XS": "17-710", "XS": "17-711", "S": "17-712", "M": "17-713", "L": "17-714", "XL": "17-715", "2XL": "17-716", "3XL": "17-717"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE NO VISOR",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 78.09,
        "skus": {"2XS": "17-720", "XS": "17-721", "S": "17-722", "M": "17-723", "L": "17-724", "XL": "17-725", "2XL": "17-726", "3XL": "17-726-7"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE NO VISOR",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 78.09,
        "skus": {"2XS": "17-730", "XS": "17-731", "S": "17-732", "M": "17-733", "L": "17-734", "XL": "17-735", "2XL": "17-736", "3XL": "17-736-7"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE WITH SILVER SKULL NO VSIOR",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-840", "XS": "17-841", "S": "17-842", "M": "17-843", "L": "17-844", "XL": "17-845", "2XL": "17-846"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE CARBON NO VISOR",
        "chinstrap_lock": "QR",
        "color": "DULL",
        "price": 108.89,
        "skus": {"2XS": "17-737", "XS": "17-737-1", "S": "17-737-2", "M": "17-737-3", "L": "17-737-4", "XL": "17-737-5", "2XL": "17-737-6"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE CARBON BIG CHECKS NO VISOR",
        "chinstrap_lock": "QR",
        "color": "DULL",
        "price": 115.49,
        "skus": {"2XS": "17-800", "XS": "17-801", "S": "17-802", "M": "17-803", "L": "17-804", "XL": "17-805", "2XL": "17-806"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT BEANIE",
        "submodel": "DOT QR BEANIE CARBON BIG CHECKS NO VISOR",
        "chinstrap_lock": "QR",
        "color": "GLOSS",
        "price": 115.49,
        "skus": {"2XS": "17-810", "XS": "17-811", "S": "17-812", "M": "17-813", "L": "17-814", "XL": "17-815", "2XL": "17-816"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT POLO",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 74.79,
        "skus": {"2XS": "17-080", "XS": "17-081", "S": "17-082", "M": "17-083", "L": "17-084", "XL": "17-085", "2XL": "17-086"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT POLO",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 74.79,
        "skus": {"2XS": "17-090", "XS": "17-091", "S": "17-092", "M": "17-093", "L": "17-094", "XL": "17-095", "2XL": "17-096"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT POLO CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL",
        "price": 104.49,
        "skus": {"2XS": "17-280", "XS": "17-281", "S": "17-282", "M": "17-283", "L": "17-284", "XL": "17-285", "2XL": "17-286"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT GERMAN",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 74.79,
        "skus": {"2XS": "17-060", "XS": "17-061", "S": "17-062", "M": "17-063", "L": "17-064", "XL": "17-065", "2XL": "17-066"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT GERMAN",
        "chinstrap_lock": "DR",
        "color": "GLOSS BALCK",
        "price": 74.79,
        "skus": {"2XS": "17-070", "XS": "17-071", "S": "17-072", "M": "17-073", "L": "17-074", "XL": "17-075", "2XL": "17-076"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT GERMAN CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL",
        "price": 104.49,
        "skus": {"2XS": "17-260", "XS": "17-261", "S": "17-262", "M": "17-263", "L": "17-264", "XL": "17-265", "2XL": "17-266"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT X-TERMINTOR",
        "submodel": "DOT X-TERMINTOR",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 79.19,
        "skus": {"2XS": "17-098", "XS": "17-098-1", "S": "17-098-2", "M": "17-098-3", "L": "17-098-4", "XL": "17-098-5", "2XL": "17-098-6"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT X-TERMINTOR",
        "submodel": "DOT X-TERMINTOR",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 79.19,
        "skus": {"2XS": "17-099", "XS": "17-099-1", "S": "17-099-2", "M": "17-099-3", "L": "17-099-4", "XL": "17-099-5", "2XL": "17-099-6"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT QR POLO",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 78.09,
        "skus": {"2XS": "17-780", "XS": "17-781", "S": "17-782", "M": "17-783", "L": "17-784", "XL": "17-785", "2XL": "17-786", "3XL": "786-7"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT QR POLO",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 78.09,
        "skus": {"2XS": "17-790", "XS": "17-791", "S": "17-792", "M": "17-793", "L": "17-794", "XL": "17-795", "2XL": "17-796", "3XL": "796-7"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT POLO",
        "submodel": "DOT QR POLO CARBON",
        "chinstrap_lock": "QR",
        "color": "DULL",
        "price": 108.89,
        "skus": {"2XS": "17-797", "XS": "17-797-1", "S": "17-797-2", "M": "17-797-3", "L": "17-797-4", "XL": "17-797-5", "2XL": "17-797-6"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT QR GERMAN",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 78.09,
        "skus": {"2XS": "17-760", "XS": "17-761", "S": "17-762", "M": "17-763", "L": "17-764", "XL": "17-765", "2XL": "17-766"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT QR GERMAN",
        "chinstrap_lock": "QR",
        "color": "GLOSS BALCK",
        "price": 78.09,
        "skus": {"2XS": "17-770", "XS": "17-771", "S": "17-772", "M": "17-773", "L": "17-774", "XL": "17-775", "2XL": "17-776"}
    },
    {
        "subcategory": "HALF FACE",
        "model_family": "DOT GERMAN",
        "submodel": "DOT QR GERMAN CARBON",
        "chinstrap_lock": "QR",
        "color": "DULL",
        "price": 108.89,
        "skus": {"2XS": "17-777", "XS": "17-777-1", "S": "17-777-2", "M": "17-777-3", "L": "17-777-4", "XL": "17-777-5", "2XL": "17-777-6"}
    },

    # --- 3/4 OPEN FACE ---
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 79.19,
        "skus": {"2XS": "17-100", "XS": "17-101", "S": "17-102", "M": "17-103", "L": "17-104", "XL": "17-105", "2XL": "17-106"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "DR",
        "color": "GLOSS BLACK",
        "price": 79.19,
        "skus": {"2XS": "17-110", "XS": "17-111", "S": "17-112", "M": "17-113", "L": "17-114", "XL": "17-115", "2XL": "17-116"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "DR",
        "color": "GLOSS WHITE",
        "price": 79.19,
        "skus": {"2XS": "17-158", "XS": "17-158-1", "S": "17-158-2", "M": "17-158-3", "L": "17-158-4", "XL": "17-158-5", "2XL": "17-158-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK / ORANGE STRIPES",
        "price": 79.19,
        "skus": {"2XS": "17-159", "XS": "17-159-1", "S": "17-159-2", "M": "17-159-3", "L": "17-159-4", "XL": "17-159-5", "2XL": "17-159-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL WITH BLACK STRIPES",
        "price": 109.99,
        "skus": {"2XS": "17-290", "XS": "17-291", "S": "17-292", "M": "17-293", "L": "17-294", "XL": "17-295", "2XL": "17-296"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-740", "XS": "17-741", "S": "17-742", "M": "17-743", "L": "17-744", "XL": "17-745", "2XL": "17-746"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "QR",
        "color": "GLOSS BLACK",
        "price": 80.29,
        "skus": {"2XS": "17-750", "XS": "17-751", "S": "17-752", "M": "17-753", "L": "17-754", "XL": "17-755", "2XL": "17-756"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "QR",
        "color": "GLOSS WHITE",
        "price": 80.29,
        "skus": {"2XS": "17-163", "XS": "17-163-1", "S": "17-163-2", "M": "17-163-3", "L": "17-163-4", "XL": "17-163-5", "2XL": "17-163-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK / ORANGE STRIPES",
        "price": 80.29,
        "skus": {"2XS": "17-164", "XS": "17-164-1", "S": "17-164-2", "M": "17-164-3", "L": "17-164-4", "XL": "17-164-5", "2XL": "17-164-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE CARBON",
        "chinstrap_lock": "QR",
        "color": "DULL WITH BLACK STRIPES",
        "price": 112.19,
        "skus": {"2XS": "17-757", "XS": "17-757-1", "S": "17-757-2", "M": "17-757-3", "L": "17-757-4", "XL": "17-757-5", "2XL": "17-757-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE CARBON BIG CHECKS",
        "chinstrap_lock": "QR",
        "color": "DULL WITH BLACK STRIPES",
        "price": 119.89,
        "skus": {"2XS": "17-820", "XS": "17-821", "S": "17-822", "M": "17-823", "L": "17-824", "XL": "17-825", "2XL": "17-826"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE CARBON BIG CHECKS",
        "chinstrap_lock": "QR",
        "color": "GLOSS WITH BLACK STRIPES",
        "price": 119.89,
        "skus": {"2XS": "17-830", "XS": "17-831", "S": "17-832", "M": "17-833", "L": "17-834", "XL": "17-835", "2XL": "17-836"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT OR BEANIE",
        "submodel": "DOT OR BEANIE",
        "chinstrap_lock": "QR",
        "color": "GLOSS WHIET",
        "price": 78.09,
        "skus": {"2XS": "17-728", "XS": "17-728-1", "S": "17-728-2", "M": "17-728-3", "L": "17-728-4", "XL": "17-728-5", "2XL": "17-728-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT OR BEANIE",
        "submodel": "DOT OR BEANIE",
        "chinstrap_lock": "QR",
        "color": "DULL WINE RED",
        "price": 78.09,
        "skus": {"2XS": "17-727", "XS": "17-727-1", "S": "17-727-2", "M": "17-727-3", "L": "17-727-4", "XL": "17-727-5", "2XL": "17-727-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT OR BEANIE",
        "submodel": "DOT OR REVERSE POLO",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 78.09,
        "skus": {"2XS": "17-787", "XS": "17-787-1", "S": "17-787-2", "M": "17-787-3", "L": "17-787-4", "XL": "17-787-5", "2XL": "17-787-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "SILVER",
        "price": 97.89,
        "skus": {"2XS": "17-127", "XS": "17-127-1", "S": "17-127-2", "M": "17-127-3", "L": "17-127-4", "XL": "17-127-5", "2XL": "17-127-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "GOLD",
        "price": 97.89,
        "skus": {"2XS": "17-137", "XS": "17-137-1", "S": "17-137-2", "M": "17-137-3", "L": "17-137-4", "XL": "17-137-5", "2XL": "17-137-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "RED",
        "price": 97.89,
        "skus": {"2XS": "17-138", "XS": "17-138-1", "S": "17-138-2", "M": "17-138-3", "L": "17-138-4", "XL": "17-138-5", "2XL": "17-138-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "GREEN",
        "price": 97.89,
        "skus": {"2XS": "17-139", "XS": "17-139-1", "S": "17-139-2", "M": "17-139-3", "L": "17-139-4", "XL": "17-139-5", "2XL": "17-139-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "PINK",
        "price": 97.89,
        "skus": {"2XS": "17-160", "XS": "17-160-1", "S": "17-160-2", "M": "17-160-3", "L": "17-160-4", "XL": "17-160-5", "2XL": "17-160-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE NO STRIPES",
        "chinstrap_lock": "DR",
        "color": "BLACK",
        "price": 97.89,
        "skus": {"2XS": "17-162", "XS": "17-162-1", "S": "17-162-2", "M": "17-162-3", "L": "17-162-4", "XL": "17-162-5", "2XL": "17-162-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE WITH BLACK STRIPES",
        "chinstrap_lock": "DR",
        "color": "SILVER",
        "price": 97.89,
        "skus": {"2XS": "17-120", "XS": "17-121", "S": "17-122", "M": "17-123", "L": "17-124", "XL": "17-125", "2XL": "17-126"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE WITH BLACK STRIPES",
        "chinstrap_lock": "DR",
        "color": "GOLD",
        "price": 97.89,
        "skus": {"2XS": "17-130", "XS": "17-131", "S": "17-130-2", "M": "17-133", "L": "17-134", "XL": "17-135", "2XL": "17-136"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE WITH BLACK STRIPES",
        "chinstrap_lock": "DR",
        "color": "RED",
        "price": 97.89,
        "skus": {"2XS": "17-150", "XS": "17-151", "S": "17-152", "M": "17-153", "L": "17-154", "XL": "17-155", "2XL": "17-156"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE WITH BLACK STRIPES",
        "chinstrap_lock": "DR",
        "color": "GREEN",
        "price": 97.89,
        "skus": {"2XS": "17-157", "XS": "17-157-1", "S": "17-157-2", "M": "17-157-3", "L": "17-157-4", "XL": "17-157-5", "2XL": "17-157-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 METAL FLAKE",
        "submodel": "DOT 3/4 METAL FLAKE WITH SILVER STRIPES",
        "chinstrap_lock": "DR",
        "color": "BLACK",
        "price": 97.89,
        "skus": {"2XS": "17-161", "XS": "17-161-1", "S": "17-161-2", "M": "17-161-3", "L": "17-161-4", "XL": "17-161-5", "2XL": "17-161-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE AVIATOR WITH BROWN INT",
        "chinstrap_lock": "QR",
        "color": "WHITE",
        "price": 89.09,
        "skus": {"2XS": "17-623", "XS": "17-623-1", "S": "17-623-2", "M": "17-623-3", "L": "17-623-4", "XL": "17-623-5", "2XL": "17-623-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE AVIATOR WITH BROWN LEATHER INT",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 89.09,
        "skus": {"2XS": "17-624", "XS": "17-624-1", "S": "17-624-2", "M": "17-624-3", "L": "17-624-4", "XL": "17-624-5", "2XL": "17-624-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE AVIATOR WITH BROWN LEATHER INT",
        "chinstrap_lock": "QR",
        "color": "GLOSS BLACK",
        "price": 89.09,
        "skus": {"2XS": "17-625", "XS": "17-625-1", "S": "17-625-2", "M": "17-625-3", "L": "17-625-4", "XL": "17-625-5", "2XL": "17-625-6"}
    },
    {
        "subcategory": "3/4 OPEN FACE",
        "model_family": "DOT 3/4 OPEN FACE",
        "submodel": "DOT 3/4 OPEN FACE AVIATOR CARBON WITH BLACK LEATHER INT",
        "chinstrap_lock": "QR",
        "color": "DULL CARBON/BLACK STRIPES",
        "price": 122.09,
        "skus": {"2XS": "17-628", "XS": "17-628-1", "S": "17-628-2", "M": "17-628-3", "L": "17-628-4", "XL": "17-628-5", "2XL": "17-628-6"}
    },

    # --- FULL FACE HELMET ---
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 155.09,
        "skus": {"XS": "17-341", "S": "17-342", "M": "17-343", "L": "17-344", "XL": "17-345", "2XL": "17-346", "3XL": "17-347"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING",
        "chinstrap_lock": "DR",
        "color": "GLOSS WHITE",
        "price": 155.09,
        "skus": {"XS": "17-501", "S": "17-502", "M": "17-503", "L": "17-504", "XL": "17-505", "2XL": "17-506", "3XL": "17-507"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING",
        "chinstrap_lock": "DR",
        "color": "GLOSS BLACK",
        "price": 155.09,
        "skus": {"XS": "17-511", "S": "17-512", "M": "17-513", "L": "17-514", "XL": "17-515", "2XL": "17-516", "3XL": "17-517"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING CLASSIC",
        "chinstrap_lock": "DR",
        "color": "GLOSS WHITE/BLACK STRIPES",
        "price": 155.09,
        "skus": {"XS": "17-521", "S": "17-522", "M": "17-523", "L": "17-524", "XL": "17-525", "2XL": "17-526", "3XL": "17-527"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING RACE",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK / ORANGE STRIPES",
        "price": 155.09,
        "skus": {"XS": "17-531", "S": "17-532", "M": "17-533", "L": "17-534", "XL": "17-535", "2XL": "17-536", "3XL": "17-537"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR RACING",
        "submodel": "DOT XR RACING CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL WITH BLACK STRIPES",
        "price": 197.99,
        "skus": {"XS": "17-551", "S": "17-552", "M": "17-553", "L": "17-554", "XL": "17-555", "2XL": "17-556", "3XL": "17-557"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR SUPER STREET",
        "submodel": "DOT XR SUPER STREET",
        "chinstrap_lock": "DR",
        "color": "DULL BLACK",
        "price": 155.09,
        "skus": {"XS": "17-581", "S": "17-582", "M": "17-583", "L": "17-584", "XL": "17-585", "2XL": "17-586"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR SUPER STREET",
        "submodel": "DOT XR SUPER STREET",
        "chinstrap_lock": "DR",
        "color": "GLOSS BLACK",
        "price": 155.09,
        "skus": {"XS": "17-588-1", "S": "17-588-2", "M": "17-588-3", "L": "17-588-4", "XL": "17-588-5", "2XL": "17-588-6"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR SUPER STREET",
        "submodel": "DOT XR SUPER STREET CARBON",
        "chinstrap_lock": "DR",
        "color": "DULL WITH BLACK STRIPES",
        "price": 197.99,
        "skus": {"XS": "17-548-1", "S": "17-548-2", "M": "17-548-3", "L": "17-548-4", "XL": "17-548-5", "2XL": "17-548-6"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT RETRO MIX",
        "submodel": "DOT RETRO MIX WITH GLOSS BLACK PEAK",
        "chinstrap_lock": "QR",
        "color": "GLOSS WHITE",
        "price": 142.99,
        "skus": {"XS": "17-391", "S": "17-392", "M": "17-393", "L": "17-394", "XL": "17-395", "2XL": "17-396"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT RETRO MIX",
        "submodel": "DOT RETRO MIX WITH DULL BLACK PEAK",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 142.99,
        "skus": {"XS": "17-411", "S": "17-412", "M": "17-413", "L": "17-414", "XL": "17-415", "2XL": "17-416"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT RETRO MIX",
        "submodel": "DOT RETRO MIX WITH GLOSS BLACK PEAK",
        "chinstrap_lock": "QR",
        "color": "GLOSS BLACK",
        "price": 142.99,
        "skus": {"XS": "17-401", "S": "17-402", "M": "17-403", "L": "17-404", "XL": "17-405", "2XL": "17-406"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR LEGEND",
        "submodel": "DOT XR LEGEND WITH BROWN LEATHER INT",
        "chinstrap_lock": "QR",
        "color": "IVORY",
        "price": 164.99,
        "skus": {"XS": "17-620-1", "S": "17-620-2", "M": "17-620-3", "L": "17-620-4", "XL": "17-620-5", "2XL": "17-620-6", "3XL": "17-620-7"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT XR LEGEND",
        "submodel": "DOT XR LEGEND WITH BROWN LEATHER INT",
        "chinstrap_lock": "QR",
        "color": "GLOSS BLACK",
        "price": 164.99,
        "skus": {"XS": "17-622-1", "S": "17-622-2", "M": "17-622-3", "L": "17-622-4", "XL": "17-622-5", "2XL": "17-622-6", "3XL": "17-622-7"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT MODULAR FLIP-UP",
        "submodel": "DOT MODULAR FLIP-UP",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 109.99,
        "skus": {"XS": "17-351", "S": "17-352", "M": "17-353", "L": "17-354", "XL": "17-355", "2XL": "17-356", "3XL": "17-357"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT MODULAR FLIP-UP",
        "submodel": "DOT MODULAR FLIP-UP",
        "chinstrap_lock": "QR",
        "color": "GLOSS BLACK",
        "price": 109.99,
        "skus": {"XS": "17-361", "S": "17-362", "M": "17-363", "L": "17-364", "XL": "17-365", "2XL": "17-366", "3XL": "17-367"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT INTEGRAL",
        "submodel": "DOT INTEGRAL WITH BROWN LEATHER SHIELD",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 164.99,
        "skus": {"XS": "17-629-1", "S": "17-629-2", "M": "17-629-3", "L": "17-629-4", "XL": "17-629-5", "2XL": "17-629-6"}
    },
    {
        "subcategory": "FULL FACE HELMET",
        "model_family": "DOT INTEGRAL",
        "submodel": "DOT INTEGRAL WITH BROWN LEATHER SHIELD",
        "chinstrap_lock": "QR",
        "color": "DULL BLACK",
        "price": 164.99,
        "skus": {"XS": "17-630-1", "S": "17-630-2", "M": "17-630-3", "L": "17-630-4", "XL": "17-630-5", "2XL": "17-630-6"}
    }
]

SIZE_MAP = {
    "2XS": 52,
    "XS": 54,
    "S": 56,
    "M": 58,
    "L": 60,
    "XL": 62,
    "2XL": 64,
    "3XL": 66
}

BRAND_ID = "PBRD26A0001"
CATEGORY_ID = "PCAT26AAAA0001"
CREATOR = "EMP26AAAA0001"

def populate():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    subcategories_col = db["product_subcategories"]
    models_col = db["product_models"]
    submodels_col = db["product_submodels"]
    variants_col = db["product_variants"]
    
    # 1. Resolve Category
    category = db["product_categories"].find_one({"category_id": CATEGORY_ID})
    if not category:
        print(f"Error: Category {CATEGORY_ID} not found.")
        return
        
    # 2. Resolve Brand
    brand = db["product_brands"].find_one({"brand_id": BRAND_ID})
    if not brand:
        print(f"Error: Brand {BRAND_ID} not found.")
        return

    subcat_cache = {}
    model_cache = {}
    submodel_cache = {}

    for row in DATA:
        subcat_name = row["subcategory"]
        model_name = row["model_family"]
        submodel_name = row["submodel"]
        
        # --- Resolve Subcategory ---
        if subcat_name not in subcat_cache:
            existing_subcat = subcategories_col.find_one({
                "name": subcat_name,
                "category_id": CATEGORY_ID
            })
            if existing_subcat:
                subcat_cache[subcat_name] = existing_subcat["subcategory_id"]
            else:
                subcat_id = generate_custom_id("PSUB", subcategories_col, "subcategory_id")
                subcat_doc = {
                    "subcategory_id": subcat_id,
                    "name": subcat_name,
                    "category_id": CATEGORY_ID,
                    "category_name": category["name"],
                    "category_status": category.get("is_active", True),
                    "category_is_active": category.get("is_active", True),
                    "is_active": True,
                    "created_by": CREATOR,
                    "created_at": get_current_time()
                }
                subcategories_col.insert_one(subcat_doc)
                subcat_cache[subcat_name] = subcat_id
                print(f"Created subcategory: {subcat_name} ({subcat_id})")
                
        subcat_id = subcat_cache[subcat_name]
        
        # --- Resolve Model ---
        model_key = (model_name, subcat_id)
        if model_key not in model_cache:
            existing_model = models_col.find_one({
                "name": model_name,
                "brand_id": BRAND_ID,
                "category_id": CATEGORY_ID,
                "subcategory_id": subcat_id
            })
            if existing_model:
                model_cache[model_key] = existing_model["model_id"]
            else:
                model_id = generate_custom_id("PMOD", models_col, "model_id")
                model_doc = {
                    "model_id": model_id,
                    "name": model_name,
                    "brand_id": BRAND_ID,
                    "brand_name": brand["name"],
                    "brand_status": brand.get("is_active", True),
                    "brand_is_active": brand.get("is_active", True),
                    "brand_image": brand.get("logo_url"),
                    "category_id": CATEGORY_ID,
                    "category_name": category["name"],
                    "category_status": category.get("is_active", True),
                    "category_is_active": category.get("is_active", True),
                    "subcategory_id": subcat_id,
                    "subcategory_name": subcat_name,
                    "subcategory_status": True,
                    "subcategory_is_active": True,
                    "is_active": True,
                    "created_by": CREATOR,
                    "created_at": get_current_time()
                }
                models_col.insert_one(model_doc)
                model_cache[model_key] = model_id
                print(f"Created model family: {model_name} ({model_id})")
                
        model_id = model_cache[model_key]
        
        # --- Resolve Submodel ---
        submodel_key = (submodel_name, model_id)
        if submodel_key not in submodel_cache:
            existing_submodel = submodels_col.find_one({
                "name": submodel_name,
                "model_id": model_id
            })
            if existing_submodel:
                submodel_cache[submodel_key] = existing_submodel["submodel_id"]
            else:
                submodel_id = generate_custom_id("PSMD", submodels_col, "submodel_id")
                is_full_face = (subcat_name == "FULL FACE HELMET")
                submodel_doc = {
                    "submodel_id": submodel_id,
                    "name": submodel_name,
                    "model_id": model_id,
                    "image": None,
                    "is_active": True,
                    "packaging_details": "6 units per carton, individual box packaging.",
                    "box_and_carton_dimensions": "Box: 36x26x26, Carton: 74x54x54" if is_full_face else "Box: 32x24x22, Carton: 68x50x48",
                    "box_weight": 1.6 if is_full_face else 1.2,
                    "box_dimension": "36x26x26" if is_full_face else "32x24x22",
                    "carton_weight": 9.8 if is_full_face else 7.8,
                    "carton_dimension": "74x54x54" if is_full_face else "68x50x48",
                    "carton_numbers": "BOX-CAR-02" if is_full_face else "BOX-CAR-01",
                    "model_name": model_name,
                    "model_status": True,
                    "model_is_active": True,
                    "brand_id": BRAND_ID,
                    "brand_name": brand["name"],
                    "created_by": CREATOR,
                    "created_at": get_current_time()
                }
                submodels_col.insert_one(submodel_doc)
                submodel_cache[submodel_key] = submodel_id
                print(f"Created submodel (graphic): {submodel_name} ({submodel_id})")
                
        submodel_id = submodel_cache[submodel_key]
        
        # --- Resolve Variants ---
        for sz_name, sku in row["skus"].items():
            if not sku or sku == "×":
                continue
                
            # Check if variant already exists
            existing_variant = variants_col.find_one({"sku_no": sku})
            if existing_variant:
                print(f"Variant SKU {sku} already exists. Skipping.")
                continue
                
            var_id = generate_custom_id("PVAR", variants_col, "variant_id")
            
            variant_doc = {
                "variant_id": var_id,
                "sku_no": sku,
                "submodel_id": submodel_id,
                "gs1_barcode": None,
                "short_description": f"{submodel_name} - {row['color']} - {sz_name}",
                "long_description": f"Classic brand B2B catalog product. Model: {model_name}. Graphic: {submodel_name}. Lock: {row['chinstrap_lock']}. Color: {row['color']}. Size: {sz_name}.",
                "carton_box_size": 1,
                "carton_barcode": None,
                "product_images": [],
                "color": row["color"],
                "size_name": sz_name,
                "size": SIZE_MAP[sz_name],
                "finish": "DULL" if "DULL" in row["color"].upper() else "GLOSS",
                "certification": ["DOT"],
                "visor_type": "CLEAR" if "WITH VISOR" in submodel_name.upper() else "NONE",
                "spoiler": "NONE",
                "chinstrap_lock": row["chinstrap_lock"],
                "pinlock": "NONE",
                "mrp": {"CAD": row["price"]},
                "is_active": True,
                "created_by": CREATOR,
                "created_at": get_current_time()
            }
            
            variants_col.insert_one(variant_doc)
            print(f"  ↳ Added Variant: {sku} ({var_id}) | Size: {sz_name} | Price: C${row['price']}")

    print("All products successfully populated!")

if __name__ == "__main__":
    populate()
