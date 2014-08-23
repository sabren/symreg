#include <cstdlib>
#include <iostream>
#include <ctime>
#include "genpy.inc.cpp"
using namespace std;

int main() {

  // initialize random number generator
  std::srand(std::time(0));

  // top level entry rule
  genpy::file_input();

  return 0;
}
