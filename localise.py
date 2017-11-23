import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import hashlib
import os
import codecs
from io import BytesIO
from zipfile import ZipFile
import geogebra
import re
session = requests.Session()

class LocalConfig(object):
    # https://stackoverflow.com/questions/2725156/ for a full list
    LINK_ATTRIBUTES = ['href', 'src']
    IGNORE_COMBOS = [['a', 'href']]

def get_resources(soup, config):
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in config.LINK_ATTRIBUTES):
            return False
        # ig
        for combo in config.IGNORE_COMBOS:
            if tag.name==combo[0] and combo[1] in tag.attrs:
                return False
        # do not rewrite self-links
        href = tag.attrs.get("href")
        if href and href[0]== "#":
            return False
        return True
            
    resources = set()
    for attribute in config.LINK_ATTRIBUTES:
        l = soup.find_all(lambda tag: is_valid_tag(tag))
        resources.update(l)
    return resources

def make_local(page_url, config=None):
    # TODO 404 handling etc.
    # TODO remove 'foo'
    try:
        os.mkdir("foo")
    except:
        pass  # TODO trap actual error only
    
    if not config:
        config = LocalConfig()
    html_response = session.get(page_url)
    
    soup = BeautifulSoup(html_response.content, 'html.parser')
    resources = get_resources(soup, config)
    # replace mathjax
    # TODO: actually install it
    mathjax, = [resource for resource in resources if 'src' in resource.attrs and "MathJax.js" in resource.attrs.get('src')]
    resources.remove(mathjax)
    mathjax.attrs['src'] = 'mathjax/MathJax.js'
    
    # replace geogebra
    """<div class="geogebra-embed-wrapper" data-ggb_id="Vxv48Gtz">...</div>"""
    geos = soup.find_all("div", {'class': 'geogebra-embed-wrapper'})
    for geo in geos:
        geo_id = geo.attrs['data-ggb_id']
        print ("downloading {}".format(geo_id))
        data = geogebra.get_zip(geo_id)
        print ("handling {}".format(geo_id))
        geo_zip = BytesIO(data)
        with ZipFile(geo_zip) as zip_file:
            # extract all files
            zip_file.extractall('foo/geogebra')
            # re-write html file...
            html_filename, = [filename for filename in zip_file.namelist() if '/' not in filename and filename.endswith('.html')]
            zip_soup = BeautifulSoup(zip_file.read(html_filename), 'html.parser')
        all_tags = zip_soup.find("body").find_all()
        wanted_tags =  zip_soup.find("body").find_all(lambda tag: tag.name == "script" or ('class' in tag.attrs and 'applet_container' in tag.attrs.get('class')))
        
        for tag in all_tags:   # ditch everything in the body, including the script and applet tags, to allow nice flat HTML structure
            tag.extract()
        
        for tag in wanted_tags:  # reinstate bits we want
            zip_soup.find("body").append(tag)
            
        # put html file back into directory
        revised_html = str(zip_soup)
        with open("foo/geogebra/_"+html_filename, "wb") as f:
            f.write(revised_html.encode('utf-8'))
        
            
        # one of these script tags has the height and width we want:
        # "width":"580","height":"630"
        
        width = None
        height = None
        for tag in wanted_tags:
            if '"width"' in tag.text:
                assert width==None
                width = re.search('"width":"(\d*)"', tag.text).groups()[0]
                height = re.search('"height":"(\d*)"', tag.text).groups()[0]
            
        # create iframe loading this page
        geo.name = "iframe"
        geo.attrs['src'] = 'geogebra/{filename}'.format(filename="_"+html_filename)
        geo.attrs['width'] = width
        geo.attrs['height'] = height
        geo.attrs['scrolling'] = 'no'
        print ("handled {}".format(geo_id))
        
        
        
        
        
    
    # note: ensure order of raw_url_list remains the same as other url_lists we later generate.
    # (hopefully there's not two different looking but identical urls)
    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources]
    full_url_list = [urljoin(page_url, resource_url) for resource_url in raw_url_list]
    # TODO: add extensions.
    hashed_file_list = [hashlib.sha1(resource_url.encode('utf-8')).hexdigest() for resource_url in full_url_list]
    replacement_list = dict(zip(raw_url_list, hashed_file_list))
    for resource in resources:
        for attribute in config.LINK_ATTRIBUTES:
            attribute_value = resource.attrs.get(attribute)
            if attribute_value in replacement_list.keys():
                resource.attrs[attribute] = replacement_list[attribute_value]
    
    for url, filename in zip(full_url_list, hashed_file_list):
        print (url)
        with open("foo/"+filename, "wb") as f:
            f.write(session.get(url, verify=False).content)
            
    with codecs.open("foo/index.html", "w", "utf-8") as f:
        # str(soup) appears to contain utf-8: "\xe2\x80\x8b" [not bytes] -- soup was based on text at this point, not content
        
        f.write(str(soup))
    
make_local("https://im.openupresources.org/7/students/5/3.html")
print("END")

