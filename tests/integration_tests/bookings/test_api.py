async def test_facilities(ac):
    response = await ac.get('/facilities/')
    assert response.status_code == 200
    assert isinstance(response.json(),list)

async def test_facilities_post(ac):
    facilities_title = 'Массаж'
    response = await ac.post('/facilities/', json={'title':facilities_title})
    assert response.status_code == 200
    res=response.json()
    assert isinstance(res,dict)
    assert 'data' in res
    assert res['data']['title'] == facilities_title