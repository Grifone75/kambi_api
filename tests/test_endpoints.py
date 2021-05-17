import json
import pytest
from kambi_api import app

"""
test set to validate pi endpoints
"""

@pytest.fixture(name='testapp')
def _test_app():
  return app


@pytest.fixture
def post_url():
	return '/api/v1/json'


@pytest.fixture
def post_data_all():
	return {
		'action':'all'
		}


@pytest.fixture
def post_data_search():
	return {
		'action':'search',
		'term':'Lisp'
		}

@pytest.fixture
def post_headers():
	mimetype = 'application/json'
	return  {
		'Content-Type': mimetype,
		'Accept': mimetype
	}


@pytest.mark.asyncio
async def test_json_endpoint_all(testapp,post_url,post_data_all,post_headers):


	client = testapp.test_client()
	response = await client.post(post_url, data=json.dumps(post_data_all), headers=post_headers)
	assert response.status_code == 200

@pytest.mark.asyncio
async def test_json_endpoint_wrong_method(testapp,post_url):

	client = testapp.test_client()
	response = await client.get(post_url)
	assert response.status_code == 405


@pytest.mark.asyncio
async def test_json_endpoint_search_missing_term(testapp,post_url,post_data_all,post_headers):

	post_data_all['action'] = 'search'

	client = testapp.test_client()
	response = await client.post(post_url, data=json.dumps(post_data_all), headers=post_headers)
	assert response.status_code == 400


@pytest.mark.asyncio
async def test_json_endpoint_search_ok(testapp,post_url,post_data_search,post_headers):

	client = testapp.test_client()
	response = await client.post(post_url, data=json.dumps(post_data_search), headers=post_headers)
	assert response.status_code == 200