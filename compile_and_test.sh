cd build/
cmake --build .
./cpp_tests/pytimeloop_cpptest ../tests/timeloop-accelergy-exercises/
cd ..
pip install -e .
python -m unittest tests/test_mapper.py