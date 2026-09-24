from src.Schemas.Schemas import HotelPost


async def test_get_hotels(ac):
    response = await ac.get('/hotels',
                            params={'date_from':'2026-08-01',
                                    'date_to':'2026-08-10'})
    print(f'{response.json()=}')
    assert response.status_code == 200