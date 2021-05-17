import pytest
from kambi_api import core_function_grep

"""
test set to validate core funtion
"""

#base parameters for search all
@pytest.fixture
def search_all_params():
	return {		
		"search":"$",
		"nresults":None
		}

#base parameters for search all with wrong dictionary
@pytest.fixture
def search_all_fail_params(search_all_params):	
	return {**search_all_params,
			"dictionary":"nonexistent.txt"}



@pytest.mark.asyncio
async def test_core_search_all_status_right(search_all_params):


	message,status = await core_function_grep(**search_all_params)
	assert status == 200


@pytest.mark.asyncio
async def test_core_search_all_status_wrong(search_all_fail_params):

	message,status = await core_function_grep(**search_all_fail_params)
	assert status == 403

