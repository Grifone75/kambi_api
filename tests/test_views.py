import pytest
from kambi_api import app

@pytest.fixture(name='testapp')
def _test_app():
  return app


@pytest.mark.asyncio
async def test_home(testapp):
    client = testapp.test_client()
    response = await client.get('/')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_wrong_url(testapp):
    client = testapp.test_client()
    response = await client.get('/wrong')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_web_api_view(testapp):
    client = testapp.test_client()
    response = await client.get('/api/v1/web')
    assert response.status_code == 200

