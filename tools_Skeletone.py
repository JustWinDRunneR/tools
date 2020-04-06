import cv2
import numpy
import tools_IO
import subprocess
import uuid
from PIL import Image, ImageDraw
import tools_image
import tools_IO
import operator
# ----------------------------------------------------------------------------------------------------------------
class Skelenonizer(object):
    def __init__(self):
        self.name = "Skelenonizer"
        self.bin_name = './images/ex_bin/Skeleton.exe'
        self.folder_out = './images/output/'
        self.data = None
        return
# ----------------------------------------------------------------------------------------------------------------
    def binarize(self,image):
        if len(image.shape)==3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        binarized = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 27, 0)
        binarized[gray>230]=255
        binarized[gray<25 ]=0

        return binarized
# ----------------------------------------------------------------------------------------------------------------
    def binarized_to_skeleton_small(self,binary_image,do_inverce=False):

        temp_bmp = str(uuid.uuid4())
        temp_txt = str(uuid.uuid4())

        if do_inverce:
            cv2.imwrite(self.folder_out+temp_bmp+'.bmp',255-binary_image)
        else:
            cv2.imwrite(self.folder_out + temp_bmp + '.bmp', binary_image)
        command = [self.bin_name,self.folder_out+temp_bmp+'.bmp',self.folder_out+temp_txt+'.txt']
        subprocess.call(command, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

        self.load_skeleton(self.folder_out+temp_txt+'.txt', binary_image.shape[0], binary_image.shape[1])
        tools_IO.remove_file(self.folder_out+temp_txt +'.txt')
        tools_IO.remove_file(self.folder_out+temp_bmp +'.bmp')
        return
# ----------------------------------------------------------------------------------------------------------------
    def create_regions(self,binary_image):
        H,W = binary_image.shape[:2]
        regions = []

        NR, NC = 2,3
        for nr in range (NR):
            rstart = 0 + H * nr / NR
            rend = 0 + H * (nr + 1) / NR
            for nc in range(NC):
                cstart = 0+W*nc/NC
                cend   = 0+W*(nc+1)/NC
                regions.append([rstart,cstart,rend,cend])

        #regions = [[0,0,400,800],[0,800,400,1600]]

        return numpy.array(regions,dtype=numpy.int)
# ----------------------------------------------------------------------------------------------------------------
    def binarized_to_skeleton_large(self,binary_image,do_inverce=False):
        regions = self.create_regions(binary_image)

        data_all = []

        for region in regions:
            temp_bmp = str(uuid.uuid4())
            temp_txt = str(uuid.uuid4())
            image_region = binary_image[region[0]:region[2],region[1]:region[3]]

            if do_inverce:
                cv2.imwrite(self.folder_out + temp_bmp + '.bmp', 255 - image_region)
            else:
                cv2.imwrite(self.folder_out + temp_bmp + '.bmp', image_region)

            command = [self.bin_name, self.folder_out + temp_bmp + '.bmp', self.folder_out + temp_txt + '.txt']
            subprocess.call(command, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

            offset = len(data_all)
            data_region = self.load_skeleton(self.folder_out + temp_txt + '.txt', image_region.shape[0], image_region.shape[1])
            shift_x = region[1]
            shift_y = region[0]

            for node in data_region:
                node[0]+=offset
                node[1]+=2*shift_x
                node[2]+=2*shift_y
                node[4]=[x+offset for x in node[4]]

            data_all+=data_region
            tools_IO.remove_file(self.folder_out+temp_txt +'.txt')
            tools_IO.remove_file(self.folder_out+temp_bmp +'.bmp')

        self.data=data_all
        self.H, self.W =  binary_image.shape[:2]
        return
# ----------------------------------------------------------------------------------------------------------------
    def load_skeleton(self,filename_in,H,W):

        self.W, self.H = W, H
        X = tools_IO.load_mat(filename_in,delim=' ',dtype=numpy.int)
        I = 0*X.copy()

        result,idx,i=[],0,0
        while i<len(X):
            n_links,x,y,w=X[i],X[i+1],X[i+2],X[i+3]
            link_ids = []
            result.append([idx,x,2*self.H-y,w,link_ids])
            I[i:i+4+n_links*2] = idx
            i+=4+n_links*2
            idx+=1

        result,idx,i=[],0,0

        while i < len(X):
            n_links,x,y,w=X[i],X[i+1],X[i+2],X[i+3]
            link_ids,c = [],0
            while (c<n_links):
                offset = X[i + 4 + c * 2]
                link_ids.append(I[offset])
                c+=1

            result.append([idx, x, 2*self.H-y, w, link_ids])
            i += 4 + n_links * 2
            idx += 1

        self.data = result

        return result
# ----------------------------------------------------------------------------------------------------------------
    def draw_skeleton(self,image_bg=None,draw_thin_lines = False,inverced=False,valid_lengths=None,valid_widths=None):
        if self.data is None:
            return

        color_white = (128,128,128)
        color_black = (32,32,32)
        color_edge =  (0,64,255)

        if inverced:
            color_white, color_black = color_black, color_white

        if image_bg is None:
            image = numpy.zeros((self.H,self.W,3),dtype=numpy.uint8)
            image[:,:] = color_white
        else:
            image = tools_image.saturate(image_bg.copy())

        pImage = Image.fromarray(image)
        draw = ImageDraw.Draw(pImage)

        dct = {}

        self.clasterize()
        n = tools_IO.max_element_by_value(self.dct_cluster_by_id)
        colors_cluster =  tools_IO.get_colors(n[1]+1,shuffle=True)

        for node in self.data:
            id1, x1, y1, w1 = node[0],node[1], node[2], node[3]
            color_line = color_edge
            #color_line = tuple(colors_cluster[self.dct_cluster_by_id[id1]])

            for nbr in node[4]:
                id2,x2,y2,w2 = self.data[nbr][0],self.data[nbr][1],self.data[nbr][2],self.data[nbr][3]
                if (1000*id1+id2 not in dct) and (1000*id2+id1 not in dct):
                    dct[1000*id1+id2]=1
                    dct[1000*id2+id1] = 1
                    w = int(min(w1,w2))
                    if image_bg is None:
                        if w%2==1:
                            draw.line(      (x1   //2,  y1    //2, x2   //2,  y2   //2),fill=color_black, width=w)
                            draw.rectangle(((x1-w)//2, (y1-w)//2, (x1+w)//2-1, (y1+w)//2-1),fill=color_black)
                            draw.rectangle(((x2-w)//2, (y2-w)//2, (x2+w)//2-1, (y2+w)//2-1),fill=color_black)
                        else:
                            draw.line(      (x1   //2,  y1   //2-1,  x2     //2,  y2//2-1), fill=color_black, width=w)
                            draw.rectangle(((x1-w)//2, (y1-w)//2  , (x1+w)//2-1, (y1+w)//2-1),fill=color_black)
                            draw.rectangle(((x2-w)//2, (y2-w)//2  , (x2+w)//2-1, (y2+w)//2-1),fill=color_black)

                    if valid_widths is not None:
                        if w in valid_widths:
                            draw.line((x1 // 2, y1 // 2 - 1, x2 // 2, y2 // 2 - 1), fill=color_line, width=w)
                    elif draw_thin_lines:
                        draw.line((x1 // 2, y1 // 2 - 1, x2 // 2, y2 // 2 - 1), fill=color_line, width=1)

                        draw.ellipse((x1 // 2 - 1, y1 // 2 - 1, x1 // 2 +1, y1 // 2 + 1 ), fill=color_line, width=1)
                        draw.ellipse((x2 // 2 - 1, y2 // 2 - 1, x2 // 2 +1, y2 // 2 + 1 ), fill=color_line, width=1)


        image = numpy.array(pImage)
        del draw
        return image
# ----------------------------------------------------------------------------------------------------------------
    def remove_edges(self,min_length=None,min_width=None):

        for node in self.data:
            id1, x1, y1, w1 = node[0], node[1], node[2], node[3]
            to_remove = []
            for nbr in node[4]:
                id2, x2, y2, w2 = self.data[nbr][0], self.data[nbr][1], self.data[nbr][2], self.data[nbr][3]
                width = int(min(w1, w2))
                length = numpy.sqrt((x1-x2)**2 + (y1-y2)**2)
                if (min_length is not None and length<min_length) or (min_width is not None and width<min_width):
                    to_remove.append(nbr)

            for i in to_remove:
                node[4].remove(i)

        self.remove_orphans()
        return
# ----------------------------------------------------------------------------------------------------------------
    def remove_orphans(self):

        new_id = 0
        dic_old_new={}
        for node in self.data:
            id1 = node[0]
            if len(node[4])>0:
                dic_old_new[id1]=new_id
                new_id+=1

        self.data = [node for node in self.data if len(node[4])>0]

        for node in self.data:
            node[4] = [dic_old_new[nbr] for nbr in node[4] if nbr in dic_old_new]
            node[0] = dic_old_new[node[0]]

        return
# ----------------------------------------------------------------------------------------------------------------
    def remove_clusters(self,min_count,min_length):
        self.clasterize()
        cnt_segm = {}
        minx,maxx,miny,maxy = {},{},{},{}
        for node_id in self.dct_cluster_by_id.keys():
            x,y = self.data[node_id][1],self.data[node_id][2]
            claster_id = self.dct_cluster_by_id[node_id]
            if claster_id not in cnt_segm:
                cnt_segm[claster_id]=1
                minx[claster_id]=x
                maxx[claster_id]=x
                miny[claster_id]=y
                maxy[claster_id]=y
            else:
                cnt_segm[claster_id]+=1
                minx[claster_id]=min(x,minx[claster_id])
                maxx[claster_id]=max(x,maxx[claster_id])
                miny[claster_id]=min(y,miny[claster_id])
                maxy[claster_id]=max(y,maxy[claster_id])

        for node in self.data:
            claster_id = self.dct_cluster_by_id[node[0]]
            cnt = cnt_segm[claster_id]
            len = numpy.sqrt((minx[claster_id]-maxx[claster_id])**2 + (miny[claster_id]-maxy[claster_id])**2)
            if cnt<min_count or len<min_length:
                node[4]=[]

        self.remove_orphans()

        return
# ----------------------------------------------------------------------------------------------------------------
    def clasterize(self):
        self.dct_cluster_by_id = {}

        cl_id=0
        for node in self.data:
            if node[0] not in self.dct_cluster_by_id:
                cl_id = self.clasterize_depth(node[0],cl_id)

        return
# ----------------------------------------------------------------------------------------------------------------
    def clasterize_depth(self,node_id,cl_id):

        node = self.data[node_id]
        if node[0] in self.dct_cluster_by_id:
            return cl_id
        self.dct_cluster_by_id[node[0]] = cl_id
        for each in node[4]:
            self.clasterize_depth(each, cl_id)

        cl_id+=1
        return cl_id
# ----------------------------------------------------------------------------------------------------------------
    def get_widts(self,X):
        Y = X^numpy.roll(X,1)
        I = numpy.array([i for i,y in enumerate(Y) if y>0])
        w = (I-numpy.roll(I,1))[1:]
        return w
# ----------------------------------------------------------------------------------------------------------------
    def get_width_distribution(self,binarized,by_column=True):

        minw, maxw = 2,10
        S = {}
        for w in range(minw, maxw + 1, 1): S[w] = 0
        if by_column:

            for c in range(binarized.shape[1]):
                W = self.get_widts(binarized[:,c])
                for w in W:
                    if w >= minw and w <= maxw:S[w]+=1
        else:

            for r in range(binarized.shape[0]):
                W = self.get_widts(binarized[r,:])
                for w in W:
                    if w >= minw and w <= maxw:S[w]+=1

        return S
# ----------------------------------------------------------------------------------------------------------------
