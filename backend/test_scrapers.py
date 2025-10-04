from high_court_scraper import HCServicesCompleteScraper
from district_court_scraper import DistrictCourtsScraper

print("Testing High Court Scraper...")
hc = HCServicesCompleteScraper()
types = hc.get_case_types()
print(f"✓ Case types loaded: {len(types)}")
print("\nSample case types:")
for i, (k, v) in enumerate(list(types.items())[:10], 1):
    print(f"  {i}. {k}: {v}")

print("\n" + "="*60)
print("Testing District Court Scraper...")
dc = DistrictCourtsScraper()
print(f"✓ District scraper created")
print(f"✓ States available: {len(dc.states)}")

print("\n✅ All tests passed!")
