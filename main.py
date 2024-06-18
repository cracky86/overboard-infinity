from fastapi import *
from fastapi.responses import *
from fastapi.staticfiles import *
from starlette.middleware.sessions import *
from starlette.middleware.base import *
from starlette.responses import *
from fastapi.templating import *

from datetime import datetime
import os
import time
import math
from PIL import Image, ImageDraw, ImageFont
import random
import threading
import json
import string
import pickle
from tripcode import tripcode
from captcha import generate_captcha_text, create_captcha
import psutil
import hashlib
import base64

# Generate a sha256 hash and encode it with url safe base64
def sha256_base64(input_string):
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()
    
    # Update the hash object with the input string encoded as bytes
    sha256_hash.update(input_string.encode('utf-8'))
    
    # Get the binary (digest) hash value
    hash_digest = sha256_hash.digest()
    
    # Encode the binary hash value to a base64 string
    base64_encoded_hash = base64.urlsafe_b64encode(hash_digest)
    
    # Convert the base64 bytes object to a string
    base64_encoded_hash_str = base64_encoded_hash.decode('utf-8')
    return(base64_encoded_hash_str)
    
browser_sessions={}

# Attempt to load configuration from file, if file not present or 
# invalid/corrupted, assume the site was started for the first time
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)

    max_upload_size = config["MAX_UPLOAD"]
    UPLOAD_FOLDER = config["UPLOAD_FOLDER"]
    disable_captcha = config["DISABLE_CAPTCHA"]
    enable_tripcodes = config["ENABLE_TRIPCODE"]
    image_required = config["REQUIRE_IMAGE"]
    title_required = config["REQUIRE_TITLE"]
    disable_image = config["DISABLE_IMAGE"]
    mods = config["ADMINS"]
    first_start = False
except:
    first_start = True

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Catch requests over a certain size and redirect to an error page
if not first_start:
    class LimitUploadSizeMiddleware(BaseHTTPMiddleware): 
        def __init__(self, app, max_upload_size: int):
            super().__init__(app)
            self.max_upload_size = max_upload_size

        async def dispatch(self, request: Request, call_next):
            if request.method == "POST" or request.method == "PUT":
                if request.headers.get("content-length"):
                    content_length = int(request.headers["content-length"])
                    if content_length > self.max_upload_size:
                        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "File too large"})
            return await call_next(request)
    app.add_middleware(LimitUploadSizeMiddleware, max_upload_size=max_upload_size)

def load_config_from_file(file_name):
    raise NotImplementedError

# Interpolate between 2 colors based on the 't' variable
def interpolate_color(color1, color2, t):
    # Ensure t is within the valid range
    t = max(0, min(1, t))

    # Interpolate each channel
    r = int(color1[0] + (color2[0] - color1[0]) * t)
    g = int(color1[1] + (color2[1] - color1[1]) * t)
    b = int(color1[2] + (color2[2] - color1[2]) * t)
    return ((r,g,b))

# Memory usage image
# Image is displayed on site showing the memory usage of the python app, and total system memory usage
def memory_usage():
    image = Image.new('RGB', (128, 24), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    memory_percent = psutil.virtual_memory().percent
    usage_length = int(memory_percent / 100 * 128)
    usage=psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2
    for i in range(0,int(usage)):
        draw.line(((i,12),(i,24)), fill=interpolate_color((0,255,0),(255,0,0),i/128))
    for i in range(0, usage_length):
        t = i / 256
        color = interpolate_color((0, 255, 0), (255, 0, 0), t)
        draw.line(((i, 12), (i, 0)), fill=color)
    font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",12)
    draw.text((0,12), f"{round(usage,2)}MB", fill=(255, 255, 255), font=font)
    draw.text((0,0), f"{usage_length/256*4096}MB", fill=(255, 255, 255), font=font)
    return image

# Create a browser session
def create_session_cookie(cookie):
    global browser_sessions
    try:
        session_secret = int(cookie) # Try loading session cookie
    except:
        # Create new session and set defaults
        session_secret=random.randint(1,100000)
    if not session_secret in browser_sessions.keys():
        browser_sessions[session_secret]={"auth":False,"captcha_solved":disable_captcha,"board":0,"thread":0,"boardlogon":{},"board_authed":None,"prevpage":"/"}
    return browser_sessions[session_secret]
        

# Daemon for updating the memory usage image
def update_image():
    while True:
        image=memory_usage()
        image.save(f"files/files/assets/usage.png")
        time.sleep(15)

# Update the pickle database
def update_database():
    with open('board_db.pkl', 'wb') as f:
        pickle.dump(board, f)
    with open('get.dat', 'w') as f:
        f.write(str(get))

# On startup start the update image daemon
@app.on_event("startup")
def start_update_thread():
    threading.Thread(target=update_image, daemon=True).start()

# Mount the static files directory
app.mount("/static", StaticFiles(directory="files"), name="static")


#Load threads
try:
    with open('board_db.pkl', 'rb') as f:
        board = pickle.load(f)
    with open('get.dat', 'r') as f:
        get=int(f.read())
except Exception as err: # Assume database doesnt exist
    print(f"WARNING: load failed - {err}")
    get=0
    board = []

# Get IP of client
def get_client_ip(request: Request) -> str:
    headers_to_check = [
        "X-Forwarded-For",  # Standard header for forwarded requests
        "X-Real-IP",        # Alternative header for client IP
        "Forwarded"         # Standardized header (can contain more information)
    ]
    for header in headers_to_check:
        if header in request.headers:
            forwarded_for = request.headers[header]
            # Extract and return the first IP address found
            ip = forwarded_for.split(",")[0].strip()
            return ip
    # Fallback to request.client.host if no headers are present
    return request.client.host
def get_date():
    # Get current date and time
    current_datetime = datetime.now()

    # Extract date and time separately
    current_date = current_datetime.strftime("%Y-%m-%d")
    current_time = current_datetime.strftime("%H:%M:%S")

    return current_date, current_time

# Setup page
@app.post("/setup/")
async def setup(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    upload: int = Form(...),
    folder: str = Form(...),
    disable_captcha: bool = Form(False),
    enable_tripcodes: bool = Form(False),
    require_img: bool = Form(False),
    require_title: bool = Form(False),
    disable_img: bool = Form(False)
):
    if not first_start:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Imageboard already installed"})
    
    
    config = {
        "ADMINS": [{"name": name, "hash": sha256_base64(password)}],
        "MAX_UPLOAD": upload * 1024,
        "UPLOAD_FOLDER": "files/files",
        "DISABLE_CAPTCHA": disable_captcha,
        "ENABLE_TRIPCODE": enable_tripcodes,
        "REQUIRE_IMAGE": require_img,
        "REQUIRE_TITLE": require_title,    
        "DISABLE_IMAGE": disable_img
    }

    with open("config.json","w") as f:
        json.dump(config, f, indent=4)

    return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Please restart the server"})

# Ban middleware to manage banned users
class BanListMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = get_client_ip(request)

        # Load banlist
        with open("banlist.json", "r") as f:
            banlist = json.load(f)

        # Check if client IP is in the banlist
        if client_ip in banlist:
            ban_timestamp = datetime.fromisoformat(banlist[client_ip])
            current_time = datetime.utcnow()

            # Check if the ban is still active
            if ban_timestamp > current_time:
                return templates.TemplateResponse("ban.html", {"request": request,"date":ban_timestamp})

        response = await call_next(request)
        return response
app.add_middleware(BanListMiddleware)
def add_ip_to_banlist(ip: str, ban_until: str):
    """
    Adds an IP address to the banlist.json file with a specified ban expiration timestamp.

    :param ip: The IP address to be banned.
    :param ban_until: The ban expiration timestamp in ISO format (e.g., '2024-12-31T23:59:59').
    """
    try:
        # Parse the provided ban_until date to ensure it's valid ISO 8601 format
        ban_until_datetime = datetime.fromisoformat(ban_until)

        # Load the existing banlist
        try:
            with open("banlist.json", "r") as f:
                banlist = json.load(f)
        except FileNotFoundError:
            banlist = {}

        # Add or update the IP in the banlist
        banlist[ip] = ban_until_datetime.isoformat()

        # Write the updated banlist back to the file
        with open("banlist.json", "w") as f:
            json.dump(banlist, f, indent=4)

        print(f"IP {ip} has been banned until {ban_until}.")
    except ValueError as err:
        print(f"Invalid date format: {err}. Please use ISO format (e.g., '2024-12-31T23:59:59').")
    except json.JSONDecodeError as err:
        print(f"Error reading JSON file: {err}.")
    except Exception as err:
        print(f"An unexpected error occurred: {err}")
@app.post("/makeboard/")
async def make_board(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    boardname: str = Form(...),
    boardpass: str = Form(""),
    enable_tripcodes: bool = Form(False),
    require_img: bool = Form(False),
    require_title: bool = Form(False),
    disable_img: bool = Form(False),
    captcha: str = Form(...),
    cookie = Cookie(None)
):
    global board,browser_sessions
    session_secret=int(cookie)
    if browser_sessions[session_secret]["captcha_text"]!=captcha:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Invalid CAPTCHA"})
    for i in board:
        if i["boardname"]==boardname:
            return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Board already exists"})
    
    board.append({"id":len(board),"ip":get_client_ip(request),"admin_name":name,"password":sha256_base64(password),"boardname":boardname,"boardpass":boardpass,"enable_trip":enable_tripcodes,"require_img":require_img,"require_title":require_title,"disable_img":disable_img,"threads":[]})
    update_database()
    return RedirectResponse(url="/", status_code=302)

# Return installation page of the imageboard
@app.get("/install", response_class=HTMLResponse)
async def install(request: Request):
    # The page will only be able to be accessed on the first start
    if not first_start:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Imageboard already installed"})
    return templates.TemplateResponse("setup.html", {"request": request})

@app.get("/newboard", response_class=HTMLResponse)
async def makeboard(request: Request, response:Response,cookie = Cookie(None)):
    global browser_sessions
    session_secret = int(cookie)
    session=browser_sessions[session_secret]
    return templates.TemplateResponse("createboard.html", {"request": request,"session":session})


@app.get("/thread/", response_class=HTMLResponse)
async def dynamic_page(request: Request, response: Response,cookie = Cookie(None)): # View and interact with a thread
    if first_start:
        return RedirectResponse(url="/install/", status_code=302)
    global browser_sessions,board
    start_time = time.perf_counter() # Used for measuring load time
    create_session_cookie(cookie)
    session_secret = int(cookie)
    logon=False
    if browser_sessions[session_secret]["board"] in browser_sessions[session_secret]["boardlogon"]:
        if browser_sessions[session_secret]["boardlogon"][browser_sessions[session_secret]["board"]]==board[int(browser_sessions[session_secret]["board"])]["boardpass"]:
            print("krunk")
            logon=True
    if board[int(browser_sessions[session_secret]["board"])]["boardpass"]=="":
        logon=True
    if not logon:
        return templates.TemplateResponse("boardpass.html", {"request": request,"session":browser_sessions[session_secret]})
    
    if browser_sessions[session_secret]["board_authed"]  == browser_sessions[session_secret]["board"]:
        permissions = 1
    elif browser_sessions[session_secret]["auth"]:
        permissions = 2
    else:
        permissions = 0
    # Generate captcha and save it to the captcha folder
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"
    
    solved=browser_sessions[session_secret]["captcha_solved"]
    browser_sessions[session_secret]["prevpage"]="../thread/"
    # Try/catch used to prevent edge cases where an user accesses /thread/ with no thread existing, or a bad "board" value in browser_sessions
    try:
        boardlist=[] # Save thread titles and ids here for displaying on the sidebar
        print(board)
        for i in board[int(browser_sessions[session_secret]["board"])]["threads"]:
            print(type(i))
            boardlist.append({"title":i["title"],"id":i["id"]})
        
        thread_head=board[browser_sessions[session_secret]["board"]]["threads"]
        
        posts=board[int(browser_sessions[session_secret]["board"])]["threads"] # Load all replies to a thread
        
        #Profiling end, display the resulting time
        end_time = time.perf_counter() 
        rendering_time = end_time - start_time
        print("Rendering time:", rendering_time, "seconds")
        
        t_response=templates.TemplateResponse("catalog.html", {"authed":permissions,"threadhead":thread_head,"request": request, "posts": posts,"boards":boardlist,"session":browser_sessions[session_secret],"time":round(rendering_time,3),"is_solved":solved},response=response)

        return t_response
    except Exception as err:
        print(err)
        return RedirectResponse(url="/", status_code=302)
@app.get("/get-ip")
async def get_ip(request: Request):
    ip = get_client_ip(request)
    return {"ip": ip}
@app.get("/", response_class=HTMLResponse)
async def boardlist(request: Request, response: Response,cookie = Cookie(None)): # Board view that shows all threads
    if first_start:
        return RedirectResponse(url="/install/", status_code=302)
    global browser_sessions,board
    
    start_time = time.perf_counter() # Start profiling load time of the page

    
    create_session_cookie(cookie)    
    try:
        session_secret = int(cookie) # Try loading session cookie
    except:
        # Create new session and set defaults
        session_secret=random.randint(1,100000)
    if not session_secret in browser_sessions.keys():
        browser_sessions[session_secret]={"auth":False,"captcha_solved":disable_captcha,"board":0,"thread":0,"boardlogon":{},"board_authed":None,"prevpage":"/"}

    # Generate and save captcha
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"
    solved=browser_sessions[session_secret]["captcha_solved"]
    
    usage = memory_usage()
    usage.save(f"files/files/assets/usage.png")
    
    board_id_list=[]
    threadlist=[]
    print(board)
    for i in board:
        threadlist.append({"title":i["boardname"]})
    
    # End profiling and display time
    end_time = time.perf_counter()
    rendering_time = end_time - start_time
    print("Rendering time:", rendering_time, "seconds")
    
    t_response=templates.TemplateResponse("boards.html", {"authed":browser_sessions[session_secret]["auth"],"request": request, "posts": board,"threads":threadlist,"session":browser_sessions[session_secret],"time":round(rendering_time,3),"is_solved":solved},response=response)
    t_response.set_cookie(key="cookie", value=str(session_secret),httponly=True) # Set the session cookie

    return t_response

@app.get("/threadview/", response_class=HTMLResponse)
async def threadview(request: Request, response: Response,cookie = Cookie(None)): # Board view that shows all threads
    if first_start:
        return RedirectResponse(url="/install/", status_code=302)
    global browser_sessions,board
    
    start_time = time.perf_counter() # Start profiling load time of the page

    
    
    try:
        session_secret = int(cookie) # Try loading session cookie
    except:
        # Create new session and set defaults
        session_secret=random.randint(1,100000)
    if not session_secret in browser_sessions.keys():
        browser_sessions[session_secret]={"auth":False,"captcha_solved":disable_captcha,"board":0}
    browser_sessions[session_secret]["prevpage"]="../threadview/"
    # Generate and save captcha
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"
    solved=browser_sessions[session_secret]["captcha_solved"]
    
    usage = memory_usage()
    usage.save(f"files/files/assets/usage.png")
    
    board_id_list=[]
    threadlist=[]
    for i in board[int(browser_sessions[session_secret]["board"])]["threads"]:
        threadlist.append({"title":i["title"],"id":i["id"]})
    
    # End profiling and display time
    end_time = time.perf_counter()
    rendering_time = end_time - start_time
    print("Rendering time:", rendering_time, "seconds")
    
    t_response=templates.TemplateResponse("index.html", {"authed":browser_sessions[session_secret]["auth"],"request": request, "posts": board[int(browser_sessions[session_secret]["board"])]["threads"][int(browser_sessions[session_secret]["thread"])]["thread"],"threadhead": board[int(browser_sessions[session_secret]["board"])]["threads"][int(browser_sessions[session_secret]["board"])],"threads":threadlist,"session":browser_sessions[session_secret],"time":round(rendering_time,3),"is_solved":solved},response=response)
    t_response.set_cookie(key="cookie", value=str(session_secret),httponly=True) # Set the session cookie

    return t_response

# Delete post
@app.post("/delete", response_class=HTMLResponse)
async def delete(request: Request, post_ids: list[int] = Form([]), passw: str = Form(""), ban: str = Form(None), cookie: int = Cookie(None)):
    global get,banned_users
    
    # Check if no post IDs are provided
    if not post_ids:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "No selected posts"})
    
    # Retrieve session details
    session_secret = int(cookie)
    session_data = browser_sessions.get(session_secret, {})
    auth = session_data.get("auth", False)
    boardauth = session_data.get("board_authed", -1) == session_data.get("board", -2)
    board_name = browser_sessions[session_secret]["thread"]

    # Check if authenticated as admin
    if passw == "" and not auth:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Post cannot be deleted"})
        
    ban_user = ban == "ban"  # Convert ban checkbox to boolean
    # Attempt to delete posts from the thread

    if type(board_name)==int:
        try:
            board_posts = board[board_name - 1]["thread"]
            for post_id in post_ids:
                for index, post in enumerate(board_posts):
                    if post["id"] == post_id:
                        post_passw = post.get("password")
                        if post_passw == passw or auth or boardauth:
                            if ban_user and auth:
                                add_ip_to_banlist(post["ip"],'2124-12-31T23:59:59')
                            del board_posts[index]
                            get -= 1
                            break
                        else:
                            return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"})
        except Exception as e:
            # Log exception or handle specific cases if needed
            pass

    # Attempt to delete threads
    try:
        # Iterate through posts marked for deletion
        for post_id in post_ids:
            for index, post in enumerate(board[browser_sessions[session_secret]["board"]]["threads"]):
                # Remove selected post if post id matches
                print(post["id"])
                if post["id"] == post_id:
                    post_passw = post.get("password")
                    if post_passw == passw or auth or boardauth:
                        if ban_user and auth:
                            print(post["ip"])
                            add_ip_to_banlist(post["ip"],'2025-12-31T23:59:59')
                        get -= len(board[browser_sessions[session_secret]["board"]]["threads"][index]["thread"])
                        del board[browser_sessions[session_secret]["board"]]["threads"][index]
                        get -= 1
                        break
                    else:
                        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"})
    except Exception as e:
        # Log exception or handle specific cases if needed
        pass

    # Update the database after deletion
    update_database()
    
    # Redirect to home page after successful deletion
    return RedirectResponse(url="/thread", status_code=302)

# Delete post
@app.post("/delboard", response_class=HTMLResponse)
async def deleteboard(request: Request, post_ids: list[str] = Form([]), passw: str = Form(""), ban: bool = Form(""), cookie: int = Cookie(None)):
    global get,banned_users,board
    
    # Check if no post IDs are provided
    if not post_ids:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "No selected posts"})
    
    # Retrieve session details
    session_secret = int(cookie)
    session_data = browser_sessions.get(session_secret, {})
    auth = session_data.get("auth", False)
    board_name = browser_sessions[session_secret]["thread"]

    # Check if authenticated as admin
    if passw == "" and not auth:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Post cannot be deleted"})

    # Attempt to delete posts from the thread
    
    # retarded solution for a retarded problem
    # TODO: make this not retarded
    try:
        for post_id in post_ids:
            for index, post in enumerate(board):
                if post["boardname"] == post_id:
                    post_passw = post.get("password")
                    print(post_passw,sha256_base64(passw))
                    if post_passw == sha256_base64(passw) or auth:
                        print("success")
                        if ban:
                            banned_users.append(post["ip"])
                        del board[index]
                        break
                    else:
                        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"})

    except Exception as e:
        # Log exception or handle specific cases if needed
        pass

    # Update the database after deletion
    update_database()
    
    # Redirect to home page after successful deletion
    return RedirectResponse(url="/", status_code=302)

# Change selected thread
@app.get("/board/{board_name}", response_class=HTMLResponse)
async def goto_board(board_name, request: Request, cookie = Cookie(None)):
    create_session_cookie(cookie)
    session_secret = int(cookie) # Load session secret
    
    j=0
    for i in board[int(browser_sessions[session_secret]["board"])]["threads"]: # Find the id of the provided thread name
        if i["id"]==int(board_name):
            break
        j+=1
    browser_sessions[session_secret]["thread"]=j

    return RedirectResponse(url="/threadview/", status_code=302) # Go to thread view page

@app.get("/goboard/{board_name}", response_class=HTMLResponse)
async def goto_board(board_name, request: Request, cookie = Cookie(None)):
    global browser_sessions
    create_session_cookie(cookie)
    session_secret = int(cookie) # Load session secret
    # Generate and save captcha
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"

    for i in board: # Find the id of the provided thread name
        if i["boardname"]==board_name:
            j=i["id"]
            break
    print(j)
    browser_sessions[session_secret]["board"]=j
    try:
        if board[j]["boardpass"]=="":
            return RedirectResponse(url="/thread/", status_code=302) # Go to thread view page
        if j in browser_sessions[session_secret]["boardlogon"]:
            if browser_sessions[session_secret]["boardlogon"][j]==board[j]["boardpass"] or board[j]["boardpass"]=="":
                return RedirectResponse(url="/thread/", status_code=302) # Go to thread view page
    except Exception as err:
        print(err)
        pass
    return templates.TemplateResponse("boardpass.html", {"request": request,"session":browser_sessions[session_secret]})
   
# Login page
@app.get("/boardlogin", response_class=HTMLResponse)
async def boardlogin(request: Request, cookie = Cookie(None)):
    create_session_cookie(cookie)
    session_secret = int(cookie)
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"
    if browser_sessions[session_secret]["board_authed"]==browser_sessions[session_secret]["board"]:
        return templates.TemplateResponse("logout.html", {"request": request,"name":""})
    return templates.TemplateResponse("loginboard.html", {"request": request,"session":browser_sessions[session_secret]}) # Send to login page   

# Login page
@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, cookie = Cookie(None)):
    create_session_cookie(cookie)
    session_secret = int(cookie)
    captcha_text = generate_captcha_text()
    captcha_image = create_captcha(captcha_text)
    captcha_image.save(f"files/files/captcha/{sha256_base64(str(session_secret)+'nonce')}.png")
    browser_sessions[session_secret]["captcha_text"]=captcha_text
    browser_sessions[session_secret]["captcha_img"]=f"{sha256_base64(str(session_secret)+'nonce')}.png"
    if browser_sessions[session_secret]["auth"]:
        return templates.TemplateResponse("logout.html", {"request": request,"name":""})
    return templates.TemplateResponse("mod.html", {"request": request,"session":browser_sessions[session_secret]}) # Send to login page

# Log out and return to main page
@app.post("/logout", response_class=HTMLResponse)
async def logout(request: Request, cookie = Cookie(None)):
    global browser_sessions
    session_secret = int(cookie)
    browser_sessions[session_secret]["auth"]=False
    browser_sessions[session_secret]["board_authed"]=None
    return RedirectResponse(url="/", status_code=302)



# Verify username and password
@app.post("/verify", response_class=HTMLResponse)
async def verify(request: Request, name: str = Form(""), password=Form(""),captcha=Form(""),cookie = Cookie(None)):
    
    global browser_sessions
    create_session_cookie(cookie)
    session_secret = int(cookie)
    captcha_text = browser_sessions[session_secret]["captcha_text"]
    if name==None: 
        return templates.TemplateResponse("login.html", {"request": request})
    if captcha!=captcha_text and not disable_captcha: # Check if CAPTCHA is correct
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong CAPTCHA"})
    
    if browser_sessions[session_secret]["auth"]: # If authenticated, skip verification and return to main page
        return RedirectResponse(url="/", status_code=302)
    for i in mods: # Verify if the user actually exists, and compute a hash from the user's password
        if i["name"] == name and i["hash"] == sha256_base64(password):
            browser_sessions[session_secret]["auth"]=True # Set auth flag to true, and return to main page
            return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"}) # If the check fails on every loop iteration, assume the password or username was incorrect

# Verify username and password
@app.post("/verifyboardlogon", response_class=HTMLResponse)
async def verifyboardlogon(request: Request, name: str = Form(""), password=Form(""),captcha=Form(""),cookie = Cookie(None)):
    
    global browser_sessions
    session_secret = int(cookie)
    captcha_text = browser_sessions[session_secret]["captcha_text"]
    if name==None: 
        return templates.TemplateResponse("loginboard.html", {"request": request})
    if captcha!=captcha_text and not disable_captcha: # Check if CAPTCHA is correct
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong CAPTCHA"})
    
    if browser_sessions[session_secret]["board_authed"]==browser_sessions[session_secret]["board"]: # If authenticated, skip verification and return to main page
        return RedirectResponse(url="/thread", status_code=302)
    if board[browser_sessions[session_secret]["board"]]["admin_name"] == name and board[browser_sessions[session_secret]["board"]]["password"] == sha256_base64(password):
        browser_sessions[session_secret]["board_authed"]=browser_sessions[session_secret]["board"] # Set auth flag to true, and return to main page
        return RedirectResponse(url="/thread", status_code=302)
    return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"}) # If the check fails on every loop iteration, assume the password or username was incorrect

# Verify board password
@app.post("/verifyboardpass", response_class=HTMLResponse)
async def verifyboardpass(request: Request, password=Form(""),captcha=Form(""),cookie = Cookie(None)):
    
    global browser_sessions,board
    session_secret = int(cookie)
    captcha_text = browser_sessions[session_secret]["captcha_text"]
    if captcha!=captcha_text and not disable_captcha: # Check if CAPTCHA is correct
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong CAPTCHA"})
    print(browser_sessions[session_secret])        
    if browser_sessions[session_secret]["auth"]: # If authenticated, skip verification and return to main page
        
        return RedirectResponse(url="/thread", status_code=302)
    if board[int(browser_sessions[session_secret]["board"])]["boardpass"] == password:
        browser_sessions[session_secret]["boardlogon"][browser_sessions[session_secret]["board"]]=password
        return RedirectResponse(url="/thread", status_code=302)
    return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": "Wrong password"}) # If the check fails on every loop iteration, assume the password or username was incorrect


# Post replies to a thread
@app.post("/post", response_class=HTMLResponse)
async def process_post(request: Request, title: str = Form(""), name: str = Form("Anonymous"), comment: str = Form(""), file: UploadFile = File(""),captcha: str = Form(""),password=Form(""),cookie = Cookie(None)):
    global board,browser_sessions,get
    
    # If an exception is raised, send the user to an error page
    # For invalid forms, raise an exception with a meaningful error message
    try:
        # Verify captcha if enabled
        session_secret = int(cookie) 
        captcha_text = browser_sessions[session_secret]["captcha_text"]
        if not browser_sessions[session_secret]["captcha_solved"]: # Verify captcha if not solved already
            if captcha == "": # User left empty field
                raise Exception("No captcha provided")
            if captcha != captcha_text: # User mistyped the captcha
                print(captcha_text)
                raise Exception("Invalid captcha")
            else: # The verification is successful, set the session flag
                browser_sessions[session_secret]["captcha_solved"]=False

        # Disallow empty comments
        if comment == "":
            raise Exception("Post cannot be empty")
        
        # Disallow ! in name, as its used as a tripcode seperator
        # Prevents impersonating tripcode users
        if "!" in name:
            raise Exception("Illegal character in name")
        
        # Check if tripcodes are permitted on the site
        if enable_tripcodes:
            # Split the name into the name and password
            # https://en.wikipedia.org/wiki/Imageboard#Tripcodes
            name = name.split("#", 1)
            if len(name) == 1:
                name = name[0]
            else:
                name = name[0] + "!" + tripcode(name[1])
        
        # Save uploaded file to the upload folder
        file_path=""
        if file!="":
            try:
                hasimage=not file.filename==""
                filename = str(file.filename)
                if "/" in filename:
                    raise Exception("Forbidden character in file name")
                allowed_file_types=["gif", "jpeg", "jpg", "png", "webp"]
                if not filename.split(".")[-1] in allowed_file_types:
                    raise Exception("Forbidden file extension")
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
            except:
                hasimage=False
        else:
            hasimage=False
        
        ip=get_client_ip(request)
        
        date, time = get_date()
        get+=1 # Update GET / post id 
        comment=comment.split("\n") # Split the comment into lines
        board[int(browser_sessions[session_secret]["board"])]["threads"][browser_sessions[session_secret]["thread"]]["thread"].append({"filename":filename,"title":title,"ip":ip,"author": name, "date": date, "time": time, "id": get, "content": comment, "file_path": file_path, "hasimage": hasimage,"password":password})
        
        #Update database
        update_database()
        
        #Return to thread view
        return RedirectResponse(url="/thread/", status_code=302)
    except Exception as err:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": err})

# Post new thread
@app.post("/threadpost", response_class=HTMLResponse)
async def process_threadpost(request: Request, title: str = Form(""), name: str = Form("Anonymous"), comment: str = Form(""), file: UploadFile = File(""),captcha: str = Form(""),password=Form(""),cookie = Cookie(None)):
    global board,browser_sessions,get

    # If an exception is raised, send the user to an error page
    # For invalid forms, raise an exception with a meaningful error message
    try:
        # Verify CAPTCHA if enabled
        session_secret = int(cookie)
        captcha_text = browser_sessions[session_secret]["captcha_text"]
        if not browser_sessions[session_secret]["captcha_solved"]: # If already solved, dont verify
            if captcha == "": # User didnt provide a captcha
                raise Exception("No captcha provided")
            if captcha != captcha_text: # User mistyped the captcha
                raise Exception("Invalid captcha")
            else: # Verification is successful, set the solved flag
                browser_sessions[session_secret]["captcha_solved"]=False
                
        # Forbid empty posts
        if comment == "":
            raise Exception("Post cannot be empty")
        
        # Forbid ! in name, as its a tripcode seperator
        if "!" in name:
            raise Exception("Illegal character in name")
        
        # Compute tripcode if enabled
        if enable_tripcodes:
            # Split according to seperator
            name = name.split("#", 1)
            if len(name) == 1:
                name = name[0]
            else:
                name = name[0] + "!" + tripcode(name[1])

        # Save uploaded file
        file_path=""
        if file!="":
            try:
                hasimage=True
                filename = file.filename
                if "/" in filename:
                    raise Exception("Forbidden character in file name")
                allowed_file_types=["gif", "jpeg", "jpg", "png", "webp"]
                if not filename.split(".")[-1] in allowed_file_types:
                    raise Exception("Forbidden file extension")
                if os.path.isfile(os.path.join(UPLOAD_FOLDER, filename)):
                    filename+="-"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
            except:
                hasimage=False
        elif image_required: # Throw an exception if image is required, but user didnt provide one
            raise Exception("Post must have an image")
        else:
            hasimage=False
        if title=="" and title_required:
            raise Exception("Post must have a title")
        ip=get_client_ip(request)
        # Process comment
        date, time = get_date()
        get+=1
        comment=comment.split("\n")
        board[int(browser_sessions[session_secret]["board"])]["threads"].append({"thread":[],"filename":filename,"title":title,"ip":ip,"author": name, "date": date, "time": time, "id": get, "content": comment, "file_path": file_path, "hasimage": hasimage,"password":password})
        # Update database
        update_database()
        
        # Return to home page
        return RedirectResponse(url="/thread", status_code=302)
    except Exception as err:
        return templates.TemplateResponse("error.html", {"page":browser_sessions[session_secret]["prevpage"], "request": request, "error": err})
