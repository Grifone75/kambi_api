# content of base_test.py
#just to validate the testing setup
def func(x):
    return x + 1



def test_answer_right():
    assert func(3) == 4