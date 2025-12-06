import json
from datetime import datetime, timedelta
from app.models.database import SessionLocal, Country, Price, TariffCache

def get_cached_data(pdf_url: str, max_age_days: int = 30):
    """Check if we have cached data for this PDF URL that's less than max_age_days old"""
    session = SessionLocal()
    try:
        cache = session.query(TariffCache).filter(
            TariffCache.pdf_url == pdf_url
        ).order_by(TariffCache.extracted_at.desc()).first()
        
        if cache:
            age = datetime.utcnow() - cache.extracted_at
            if age.days < max_age_days:
                return cache.data
        return None
    finally:
        session.close()

def save_to_database(pdf_url: str, data: dict):
    """Save extracted data to database"""
    session = SessionLocal()
    try:
        # Delete existing cache for this URL to avoid UPDATE operations
        session.query(TariffCache).filter(TariffCache.pdf_url == pdf_url).delete()
        
        # Delete existing countries and prices to start fresh
        session.query(Country).delete()
        session.query(Price).delete()
        
        # Save countries
        for country_data in data.get('countries', []):
            country = Country(
                name=country_data['name'],
                code=country_data['code'],
                export_zone=country_data.get('export_zone'),
                import_zone=country_data.get('import_zone')
            )
            session.add(country)
        
        # Save prices
        for service, service_data in data.get('prices', {}).items():
            for item_type in ['envelopes', 'documents', 'non_documents']:
                if item_type in service_data:
                    for price_entry in service_data[item_type]:
                        price = Price(
                            service=service,
                            item_type=item_type,
                            weight=price_entry['weight'],
                            pricing_type=price_entry.get('pricing_type', 'fixed'),
                            zones=price_entry['zones']
                        )
                        session.add(price)
        
        # Save cache entry
        cache = TariffCache(
            pdf_url=pdf_url,
            data=data
        )
        session.add(cache)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_all_data():
    """Retrieve all data from database"""
    session = SessionLocal()
    try:
        countries = session.query(Country).all()
        prices = session.query(Price).all()
        
        # Convert to dict format
        countries_list = [
            {
                'name': c.name,
                'code': c.code,
                'export_zone': c.export_zone,
                'import_zone': c.import_zone
            }
            for c in countries
        ]
        
        # Group prices by service and item_type
        prices_dict = {}
        for p in prices:
            if p.service not in prices_dict:
                prices_dict[p.service] = {'envelopes': [], 'documents': [], 'non_documents': []}
            
            price_entry = {
                'weight': p.weight,
                'zones': p.zones
            }
            if p.pricing_type != 'fixed':
                price_entry['pricing_type'] = p.pricing_type
            
            prices_dict[p.service][p.item_type].append(price_entry)
        
        return {
            'countries': countries_list,
            'prices': prices_dict
        }
    finally:
        session.close()

def export_to_json(filename: str = 'ups_data.json'):
    """Export database data to JSON file"""
    data = get_all_data()
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    return filename
