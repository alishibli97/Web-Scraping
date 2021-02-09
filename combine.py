from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import time
import requests
import io
from PIL import Image
import os
import re
import sys
import argparse
from datetime import datetime
import base64

class Image_Caption_Scraper():

    def __init__(self, headless=True, chrome_binary=None, chrome_driver='chromedriver'):
        """Initialization is only starting the web driver"""
        self.start_web_driver(headless, chrome_binary, chrome_driver)

    def start_web_driver(self, headless, chrome_binary: str=None, chrome_driver='chromedriver'):
        """Create the webdriver and point it to the specific search engine"""
        chrome_options = Options()
        chrome_options.headless = headless
        if chrome_binary is not None:
            chrome_options.binary_location = chrome_binary
        self.wd = webdriver.Chrome(options=chrome_options,executable_path=chrome_driver)

    def scrape(self,engine,num_images,query):
        """Main function to scrape"""
        self.set_target_url(query,engine)
        if engine=='google': img_data = self.get_google_images(query,num_images)
        elif engine=='yahoo': img_data = self.get_yahoo_images(query,num_images)
        elif engine=='flickr': img_data = self.get_flickr_images(query,num_images)

        self.engine = engine
        self.query = query

        return img_data

    def set_target_url(self,query,engine):
        """Given the target engine and query, build the target url"""
        self.url_index = {
            'google': "https://www.google.com/search?safe=off&site=&tbm=isch&source=hp&q={}&oq={}&gs_l=img".format(query,query),
            'yahoo': "https://images.search.yahoo.com/search/images;?&p={}&ei=UTF-8&iscqry=&fr=sfp".format(query),
            'flickr': "https://www.flickr.com/search/?text={}".format(query)
        }
        if not engine in self.url_index: sys.exit(f"Please choose {' or '.join(k for k in url_index)}.")
        self.target_url = self.url_index[engine]

    def scroll_to_end(self):
        """Function to scroll to new images after finishing all existing images"""
        print("Loading images")
        self.wd.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

    def get_google_images(self,query,num_images):
        """Retrieve urls for images and captions from Google Images search engine"""
        self.wd.get(self.target_url)   
        img_data = {}

        start = 0
        prevLength = 0
        while(len(img_data)<num_images):
            self.scroll_to_end();i=0

            thumbnail_results = self.wd.find_elements_by_css_selector("img.Q4LuWd")

            if(len(thumbnail_results)==prevLength):
                print("Loaded all images")
                break
            prevLength = len(thumbnail_results)
            print(f"There are {len(thumbnail_results)} images")
            for content in thumbnail_results[start:len(thumbnail_results)]:
                try:
                    self.wd.execute_script("arguments[0].click();", content)
                    time.sleep(0.5)

                    caption = self.wd.find_element_by_xpath('//*[@id="Sva75c"]/div/div/div[3]/div[2]/c-wiz/div/div[1]/div[3]/div[2]/a').text

                    url = self.wd.find_elements_by_css_selector('img.n3VNCb')[0]

                    if url.get_attribute('src') and not url.get_attribute('src').endswith('gif') and url.get_attribute('src') not in img_data:

                        now = datetime.now().astimezone()
                        now = now.strftime("%m-%d-%Y %H:%M:%S %z %Z")

                        img_data[len(img_data)]={
                            'url':url.get_attribute('src'),
                            'caption':caption,
                            'datetime': now,
                            'source': 'google'
                        }

                        print(f"Finished {len(img_data)} images.")
                except:
                    print("Couldn't load image/caption")
                if(len(img_data)>num_images-1): break
            start = len(thumbnail_results)

        return img_data

    def get_yahoo_images(self,query,num_images):
        """Retrieve urls for images and captions from Yahoo Images search engine"""
        self.wd.get(self.target_url)
        time.sleep(3)
        # self.wd.delete_all_cookies()
        img_data = {}

        # button = self.wd.find_element_by_name('more-res')

        # def scroll_to_end_yahoo():
        #     self.wd.execute_script("arguments[0].click();", button)
            # print("Scrolled")

        start = 0
        prevLength = 0
        enter = 0
        i=0
        while(len(img_data)<num_images):
            self.scroll_to_end()
            # scroll_to_end_yahoo()

            # html_list = self.wd.find_element_by_id("sres")
            html_list = self.wd.find_element_by_xpath('//*[@id="sres"]')
            items = html_list.find_elements_by_tag_name("li")

            if(len(items)==prevLength):
                print("Loaded all images")
                break
            prevLength = len(items)

            print(f"There are {len(items)} images")

            for content in items[start:len(items)-1]:
                try:
                    self.wd.execute_script("arguments[0].click();", content)
                    time.sleep(0.5)
                except Exception as e:
                    new_html_list = self.wd.find_element_by_id("sres")
                    new_items = new_html_list.find_elements_by_tag_name("li")
                    item = new_items[i]
                    self.wd.execute_script("arguments[0].click();", item)
                i+=1
                caption = self.wd.find_element_by_class_name('title').text

                url = self.wd.find_element_by_xpath('//*[@id="img"]')
                if url.get_attribute('src') and 'http' in url.get_attribute('src') and not url.get_attribute('src').endswith('gif') and url.get_attribute('src') not in img_data:
                    img_data[url.get_attribute('src')]=caption
                    print(f"Finished {len(img_data)} images.")
                if(len(img_data)>num_images-1): break
            start = len(items)
        return img_data
        
    def get_flickr_images(self,query,num_images):
        """Retrieve urls for images and captions from Flickr Images search engine"""
        self.wd.get(self.target_url)
        img_data = {}

        start = 0
        prevLength = 0
        waited = False
        while(len(img_data)<num_images):
            self.scroll_to_end()
            # scroll_to_end_flickr()

            items = self.wd.find_elements_by_xpath('/html/body/div[1]/div/main/div[2]/div/div[2]/div')

            if(len(items)==prevLength):
                if not waited:
                    self.wd.implicitly_wait(25)
                    waited = True
                else:
                    print("Loaded all images")
                    break
            prevLength = len(items)

            for item in items[start:len(items)-1]:
                style = item.get_attribute('style')
                url = re.search(r'url\("//(.+?)"\);',style)
                if url: 
                    url = "http://"+url.group(1)
                    caption = item.find_element_by_class_name('interaction-bar').get_attribute('title')
                    caption = caption[:re.search(r'\bby\b',caption).start()].strip()
                    img_data[url]=caption
                    print(f"Finished {len(img_data)} images.")
                if(len(img_data)>num_images-1): break
            start = len(items)
        return img_data

    def save_pictures_captions(self,img_data,out_dir):
        """Retrieve the images and save them in directory with the captions"""
        query = '_'.join(self.query.lower().split())

        os.chdir(out_dir)
        target_folder = os.path.join(f'{self.engine}',query)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        for i,val in enumerate(img_data.values()):
            print("Saving image",i)
            try:
                url = val['url']

                if(url.startswith('http')):
                    img_content = requests.get(url).content
                    img_file = io.BytesIO(img_content)
                    img = Image.open(img_file).convert('RGB')
                    file_path = os.path.join(f'{self.engine}/{query}/{i}.jpg')
                    with open(file_path,"wb") as f:
                        img.save(f,"JPEG",quality=95)
                        # print("Saved using http")
                
                elif(url.startswith('data')):
                    base64_img = url.split(',')[1]
                    base64_img_bytes = base64_img.encode('utf-8')
                    file_path = os.path.join(f'{self.engine}/{query}/{i}.jpg')
                    with open(file_path, 'wb') as f:
                        decoded_image_data = base64.decodebytes(base64_img_bytes)
                        f.write(decoded_image_data)
                    # print("Saved using base64")

            except:
                print("Couldn't save image")

        # img_data = {f'{i}.jpg': val for i,val in enumerate(img_data.values())}
        file_path = f'{self.engine}/{query}/{query}.json'
        with open(file_path, 'w+') as fp:
            json.dump(img_data, fp)
        print("Saved urls file at:",os.path.join(os.getcwd(),file_path))

    def save_json_URLS(self,img_data,out_dir):
        """Save only the meta data without the images"""
        file_path = f'{out_dir}/{self.engine}/{self.query}/{self.query}_urls.json'
        with open(file_path, 'w+') as fp:
            json.dump(img_data, fp)
        print("Saved urls file at:",os.path.join(os.getcwd(),file_path))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine',required=True,type=str)
    parser.add_argument('--num_images',required=True,type=int)
    parser.add_argument('--query',required=True,type=str)
    parser.add_argument('--out_dir',type=str,default='images')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--chrome-binary', type=str)
    parser.add_argument('--chrome-driver', type=str)
    args = parser.parse_args()

    engine = args.engine
    num_images = args.num_images
    query = args.query
    out_dir = args.out_dir
    headless = args.headless

    if args.chrome_driver is None: chrome_driver = 'chromedriver'

    scraper = Image_Caption_Scraper(headless, args.chrome_binary, chrome_driver)

    img_data = scraper.scrape(engine,num_images,query)
    scraper.save_pictures_captions(img_data,out_dir)
