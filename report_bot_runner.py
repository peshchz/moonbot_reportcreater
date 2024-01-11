import subprocess
import time

filename = 'best_bot.py'
while True:
    """However, you should be careful with the '.wait()'"""
    p = subprocess.Popen('python3 '+filename, shell=True).wait()

    """#if your there is an error from running 'best_bot.py', 
    the while loop will be repeated, 
    otherwise the program will break from the loop"""
    if p != 0:
        print('+++p != 0++')
        time.sleep(3)
        print('+++run++')
        continue
    else:
        break