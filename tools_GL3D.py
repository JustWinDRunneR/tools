#http://blog.db-in.com/cameras-on-opengl-es-2-x/
import numpy
import math
import cv2
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL import *
import OpenGL.GL.shaders
from OpenGL.GLUT import *
import glfw
import OpenGL.GL.shaders
import numpy
import pyrr
# ----------------------------------------------------------------------------------------------------------------------
import tools_IO
import tools_render_CV
import tools_wavefront
import tools_pr_geom
# ----------------------------------------------------------------------------------------------------------------------
numpy.set_printoptions(suppress=True)
numpy.set_printoptions(precision=2)
# ----------------------------------------------------------------------------------------------------------------------
class VBO(object):
    def __init__(self):
        self.n_faces = 6000
        self.id = numpy.full(9 * self.n_faces, -1)
        self.cnt = 0
        self.marker_positions = []
        self.iterator = 0
        self.color_offset  =                       3*3*self.n_faces
        self.normal_offset = self.color_offset   + 3*3*self.n_faces
        self.texture_offset = self.normal_offset + 3*3*self.n_faces
        self.data = numpy.full(self.texture_offset+3*2*self.n_faces, 0.0,dtype='float32')

        return
# ----------------------------------------------------------------------------------------------------------------------
    def append_object(self,filename_obj,mat_color,do_normalize_model_file,svec=(1,1,1),tvec=(0,0,0)):

        self.marker_positions.append(numpy.array(tvec))

        object = tools_wavefront.ObjLoader()
        object.load_mesh(filename_obj, mat_color, do_normalize_model_file)
        object.scale_mesh(svec)
        object.translate_mesh(tvec)

        clr = numpy.array([object.mat_color,object.mat_color,object.mat_color]).flatten()

        i=0
        for idxv,idxn,idxt in zip(object.idx_vertex,object.idx_normal,object.idx_texture):
            self.data[self.iterator:                    self.iterator                    +9] = (object.coord_vert[idxv]).flatten()
            self.data[self.iterator+self.color_offset  :self.iterator+self.color_offset  +9] = clr
            self.data[self.iterator+self.normal_offset :self.iterator+self.normal_offset +9] = (object.coord_norm[idxn]).flatten()
            self.data[2*self.iterator//3+self.texture_offset:2*self.iterator//3+self.texture_offset+6] = (object.coord_texture[idxt]).flatten()

            self.iterator+=9
            self.id[self.iterator:                  self.iterator + 9] = self.cnt


        self.cnt+=1

        return object
# ----------------------------------------------------------------------------------------------------------------------
    def remove_last_object(self):
        if self.cnt>1:
            self.remove_object(self.cnt-1)
            self.cnt-=1
            self.marker_positions.pop()
            return 0
        return 1
# ----------------------------------------------------------------------------------------------------------------------
    def remove_object(self,id):
        if id>0:
            idx = numpy.where(self.id==id)
            self.id[idx] = -1
            self.data[idx]=0
            self.data[[i + self.color_offset for i in idx]] = 0
            self.data[[i + self.normal_offset for i in idx]] = 0

        return
# ----------------------------------------------------------------------------------------------------------------------
class render_GL3D(object):

    def __init__(self,filename_obj,filename_texture=None,W=640, H=480,is_visible=True,do_normalize_model_file=True,projection_type='P',scale=(1,1,1)):

        glfw.init()
        self.projection_type = projection_type
        self.is_enabled_standardize_rvec = True
        self.marker_scale = 0.015
        self.scale = scale
        self.do_normalize_model_file = do_normalize_model_file
        self.bg_color  = numpy.array([76, 76, 76,1])/255
        self.mat_color = numpy.array([188, 136, 113]) / 255.0

        self.W,self.H  = W,H
        glfw.window_hint(glfw.VISIBLE, is_visible)
        self.window = glfw.create_window(self.W, self.H, "GL viewer", None, None)
        glfw.make_context_current(self.window)

        self.__init_shader()

        self.my_VBO = VBO()
        self.object = self.my_VBO.append_object(filename_obj,self.mat_color,self.do_normalize_model_file)
        self.__init_texture(filename_texture)


        self.bind_VBO()
        self.reset_view()

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_shader(self):
        # projection * view * model * transform
        # model maps from an object's local coordinate space into world space,
        # view from world space to camera space,
        # projection from camera to screen.
        vert_shader = """#version 330
                                    in layout(location = 0) vec3 position;
                                    in layout(location = 1) vec3 color;
                                    in layout(location = 2) vec3 vertNormal;
                                    in layout(location = 3) vec2 inTextureCoords;
                                    
                                    uniform mat4 transform,view,model,projection,light;
                                    out vec3 inColor;
                                    out vec3 fragNormal;
                                    out vec2 textureCoords;
                                    
                                    void main()
                                    {
                                        fragNormal = -abs((light * view * model * transform * vec4(vertNormal, 0.0f)).xyz);
                                        gl_Position = projection * view * model * transform * vec4(position, 1.0f);
                                        inColor = color;
                                        textureCoords = inTextureCoords;
                                    }"""

        frag_shader = """#version 330
                                    in vec3 inColor;
                                    in vec3 fragNormal;
                                    in vec2 textureCoords;
                                    out vec4 outColor;
                                    uniform sampler2D samplerTexture;
                                    void main()
                                    {
                                        vec3 ambientLightIntensity  = vec3(0.1f, 0.1f, 0.1f);
                                        vec3 sunLightIntensity      = vec3(1.0f, 1.0f, 1.0f);
                                        vec3 sunLightDirection      = normalize(vec3(+0.0f, -1.0f, +0.0f));
                                        vec4 texel = texture(samplerTexture, textureCoords);

                                        vec3 lightIntensity = ambientLightIntensity + sunLightIntensity * dot(fragNormal, sunLightDirection);
                                        vec4 materialColor = vec4(inColor*lightIntensity, 1);
                                        
                                        //outColor = materialColor;
                                        //outColor = texel;
                                        //outColor = texel* materialColor;
                                        outColor = vec4(texel.rgb * lightIntensity, 1);
                                        
                                    }"""

        self.shader = OpenGL.GL.shaders.compileProgram(OpenGL.GL.shaders.compileShader(vert_shader, GL_VERTEX_SHADER),
                                                       OpenGL.GL.shaders.compileShader(frag_shader, GL_FRAGMENT_SHADER))
        glUseProgram(self.shader)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_texture(self, filename_texture=None):

        if filename_texture is not None:
            texture_image = cv2.imread(filename_texture)
            texture_image = cv2.cvtColor(texture_image, cv2.COLOR_BGR2RGB)

        else:
            texture_image = numpy.full((255, 255, 3), 0, dtype=numpy.uint8)
            texture_image[:, :, 0] = int(self.mat_color[0]*255)
            texture_image[:, :, 1] = int(self.mat_color[1]*255)
            texture_image[:, :, 2] = int(self.mat_color[2]*255)


        # glBindTexture(GL_TEXTURE_2D, glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, 0)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, texture_image.shape[1], texture_image.shape[0], 0, GL_RGB,GL_UNSIGNED_BYTE, texture_image.flatten())
        glEnable(GL_TEXTURE_2D)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def bind_VBO(self):

        glBindBuffer(GL_ARRAY_BUFFER, glGenBuffers(1))

        item_size= self.my_VBO.data.itemsize

        glBufferData(GL_ARRAY_BUFFER, item_size * len(self.my_VBO.data), self.my_VBO.data, GL_STATIC_DRAW)

        # positions
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, item_size*3, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # colors
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, item_size*3, ctypes.c_void_p(item_size*self.my_VBO.color_offset))
        glEnableVertexAttribArray(1)

        # normals
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, item_size*3, ctypes.c_void_p(item_size*self.my_VBO.normal_offset))
        glEnableVertexAttribArray(2)

        #textures
        glVertexAttribPointer(3, 2, GL_FLOAT, GL_FALSE, item_size*2,ctypes.c_void_p(item_size*self.my_VBO.texture_offset))
        glEnableVertexAttribArray(3)

        glClearColor(self.bg_color[0], self.bg_color[1], self.bg_color[2], self.bg_color[3])
        glEnable(GL_DEPTH_TEST)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_projection_perspective(self,aspect_x=0.5,aspect_y=0.5):
        near, far = 1, 1000
        scale = (0.5/aspect_x)
        fx,fy = self.W/scale,self.H/scale
        width,height = self.W/scale, self.H/scale
        cx,cy = (fx/2)/scale, (fy/2)/scale




        self.mat_projection = numpy.zeros((4,4),dtype=float)

        self.mat_projection[0][0] = 2.0
        self.mat_projection[0][1] = 0.0
        self.mat_projection[0][2] = 0.0
        self.mat_projection[0][3] = 0.0

        self.mat_projection[1][0] = 0.0
        self.mat_projection[1][1] = 2.0
        self.mat_projection[1][2] = 0.0
        self.mat_projection[1][3] = 0.0

        self.mat_projection[2][0] = 1.0 - 2.0 * cx / width
        self.mat_projection[2][1] = 2.0 * cy / height - 1.0
        self.mat_projection[2][2] = (far + near) / (near - far)
        self.mat_projection[2][3] = -1.0

        self.mat_projection[3][0] = 0.0
        self.mat_projection[3][1] = 0.0
        self.mat_projection[3][2] = 2.0 * far * near / (near - far)
        self.mat_projection[3][3] = 0.0

        #aspect_x_check = 0.5 * (1 - self.mat_projection[2][0])

        glUniformMatrix4fv(glGetUniformLocation(self.shader, "projection"), 1, GL_FALSE, self.mat_projection)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_projection_ortho(self,scale_factor=(5,5)):
        fx, fy = float(self.W), float(self.H)
        near, far = 0, 1000
        scale_factor_x,scale_factor_y = scale_factor[0],scale_factor[1]
        #left, right, bottom, top = (0.25*scale_factor_x*numpy.array([-1,1,-1,1])).tolist()
        left, right, bottom, top =-0.5*scale_factor_x,+0.5*scale_factor_x,-0.5*scale_factor_y,+0.5*scale_factor_y

        self.mat_projection = pyrr.matrix44.create_orthogonal_projection(left, right, bottom, top, near, far)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "projection"), 1, GL_FALSE, self.mat_projection)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_projection(self,aspect_x=0.5,aspect_y=0.5):
        if self.projection_type == 'P':
            self.__init_mat_projection_perspective(aspect_x,aspect_y)
        else:
            self.__init_mat_projection_ortho()
        return
# ----------------------------------------------------------------------------------------------------------------------
    def init_mat_view_ETU(self, eye, target, up):

        self.eye = numpy.array(eye,dtype=numpy.float)
        self.target = numpy.array(target,dtype=numpy.float)
        self.up = numpy.array(up,dtype=numpy.float)

        self.mat_view = pyrr.matrix44.create_look_at(-self.eye , -self.target,self.up )
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "view"), 1, GL_FALSE, self.mat_view)

        #check
        #rvec, tvec = tools_pr_geom.decompose_to_rvec_tvec(self.mat_view, do_flip=True)
        #print(numpy.array(rvec), numpy.array(tvec))
        #E,T,U = tools_pr_geom.mat_view_to_ETU(self.mat_view)
        #print(numpy.array(eye,dtype=float),numpy.array(target,dtype=float),numpy.array(up,dtype=float))
        #print(numpy.array(E),numpy.array(T),numpy.array(U))
        #print()

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_view_RT(self, rvec,tvec,do_flip=True,do_rodriges=False):
        self.mat_view = tools_pr_geom.compose_RT_mat(rvec,tvec,do_flip,do_rodriges)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "view"), 1, GL_FALSE, self.mat_view)

        #check
        #rvec_view, tvec_view = tools_pr_geom.decompose_to_rvec_tvec(self.mat_view,do_flip=do_flip)
        #print(rvec,tvec)
        #print(rvec_view,tvec_view)
        #print()

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_model(self,rvec, tvec,do_rodriges=False):
        self.mat_model = tools_pr_geom.compose_RT_mat(rvec, tvec, do_flip=False, do_rodriges=do_rodriges)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "model"), 1, GL_FALSE, self.mat_model)

        # check
        #rvec_model, tvec_model = tools_pr_geom.decompose_to_rvec_tvec(self.mat_model)
        #print(rvec,tvec)
        #print(rvec_model,tvec_model)
        #print()

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_transform(self,scale_vec):
        self.mat_trns = pyrr.Matrix44.from_scale(scale_vec)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_light(self,r_vec):
        self.mat_light = pyrr.matrix44.create_from_eulers(r_vec)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "light")    , 1, GL_FALSE,self.mat_light )
        return
# ----------------------------------------------------------------------------------------------------------------------
    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glDrawArrays(GL_TRIANGLES, 0, self.my_VBO.iterator//3)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def get_image(self, do_debug=False):
        self.draw()
        image_buffer = glReadPixels(0, 0, self.W, self.H, OpenGL.GL.GL_RGB, OpenGL.GL.GL_UNSIGNED_BYTE)
        image = numpy.frombuffer(image_buffer, dtype=numpy.uint8).reshape(self.H, self.W, 3)
        image = cv2.flip(image[:,:,[2,1,0]],0)
        if do_debug:image = self.draw_debug_info(image)
        return image
# ----------------------------------------------------------------------------------------------------------------------
    def init_perspective_view0(self, rvec, tvec,aperture_x=0.5,aperture_y=0.5,scale=(1,1,1)):
        self.__init_mat_view_RT(numpy.array(rvec,dtype=float),numpy.array(tvec,dtype=float),do_rodriges=True,do_flip=True)
        self.__init_mat_model((0, 0, 0), (0, 0, 0))
        self.__init_mat_transform(scale)
        self.__init_mat_projection_perspective(aperture_x,aperture_x)
        self.eye,self.target,self.up = tools_pr_geom.mat_view_to_ETU(self.mat_view)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def init_perspective_view(self, rvec, tvec, aperture_x=0.5, aperture_y=0.5, scale=(1, 1, 1)):
        tvec = numpy.array(tvec, dtype=float)
        self.__init_mat_view_RT(numpy.array(rvec, dtype=float), tvec, do_rodriges=True,do_flip=True)
        self.__init_mat_model((0, 0, 0), (0, 0, 0))
        self.__init_mat_transform(scale)
        self.__init_mat_projection_perspective(aperture_x,aperture_x)

        self.eye, self.target, self.up = tools_pr_geom.mat_view_to_ETU(self.mat_view)
        
        return
# ----------------------------------------------------------------------------------------------------------------------
    def get_image_perspective(self, rvec, tvec, aperture_x=0.5,aperture_y=0.5,scale=(1,1,1),do_debug=False):
        self.init_perspective_view(rvec, tvec, aperture_x,aperture_y,scale)
        return self.get_image(do_debug)
# ----------------------------------------------------------------------------------------------------------------------
    def init_ortho_view(self, rvec, tvec, scale_factor):
        rvec = numpy.array(rvec)
        self.__init_mat_projection_ortho(scale_factor)
        self.__init_mat_model(rvec, tvec)
        self.__init_mat_view_RT((0, 0, 0), (0, 0, +1))
        return
# ----------------------------------------------------------------------------------------------------------------------
    def get_image_ortho(self, rvec, tvec, scale_factor, do_debug=False):
        self.init_ortho_view(rvec, tvec, scale_factor)
        return self.get_image(do_debug)
# ----------------------------------------------------------------------------------------------------------------------
    def draw_debug_info(self,image):

        result = image.copy()
        rvec_model, tvec_model, rvec_view, tvec_view = tools_pr_geom.decompose_model_view_to_RRTT(self.mat_model, self.mat_view)
        modelview = pyrr.matrix44.multiply(self.mat_model, self.mat_view)


        if self.projection_type=='P':
            #print('[ %1.2f, %1.2f, %1.2f], [%1.2f,  %1.2f,  %1.2f]' % (rvec_i[0], rvec_i[1], rvec_i[2], tvec_i[0], tvec_i[1], tvec_i[2]))
            result = tools_render_CV.draw_points_numpy_MVP(self.object.coord_vert, result, self.mat_projection,self.mat_view, self.mat_model, self.mat_trns)
        else:
            scale_factor = 1 / self.mat_projection[0, 0]
            #print('[ %1.2f, %1.2f, %1.2f], [%1.2f,  %1.2f,  %1.2f], %1.2f' % (rvec_i[0], rvec_i[1], rvec_i[2], tvec_i[0], tvec_i[1], tvec_i[2], scale_factor))
            self.draw_vec(numpy.array((scale_factor,0,0,0)), 20, 660, result)
            result = tools_render_CV.draw_points_numpy_MVP_ortho(self.object.coord_vert, result, self.mat_projection, self.mat_view, self.mat_model, self.mat_trns)


        self.draw_mat(self.mat_trns,       20, 20, result)
        self.draw_mat(self.mat_model,      20, 120, result)
        self.draw_mat(self.mat_view,       20, 220, result)
        self.draw_mat(self.mat_projection, 20, 320, result)

        return result
# ----------------------------------------------------------------------------------------------------------------------
    def draw_vec(self, V, posx, posy, image):
        if V.shape[0] == 4:
            string1 = '%+1.2f %+1.2f %+1.2f %+1.2f' % (V[0], V[1], V[2], V[3])
        else:
            string1 = '%+1.2f %+1.2f %+1.2f' % (V[0], V[1], V[2])
        image = cv2.putText(image, '{0}'.format(string1), (posx, posy), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(128, 128, 0), 1, cv2.LINE_AA)
        return image
# ----------------------------------------------------------------------------------------------------------------------
    def draw_mat(self, M, posx, posy, image):
        for row in range(M.shape[0]):
            if M.shape[1]==4:
                string1 = '%+1.2f %+1.2f %+1.2f %+1.2f' % (M[row, 0], M[row, 1], M[row, 2], M[row, 3])
            else:
                string1 = '%+1.2f %+1.2f %+1.2f' % (M[row, 0], M[row, 1], M[row, 2])
            image = cv2.putText(image, '{0}'.format(string1), (posx, posy + 20 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(128, 128, 0), 1, cv2.LINE_AA)
        return image
# ----------------------------------------------------------------------------------------------------------------------
    def stage_data(self,folder_out):
        cv2.imwrite(folder_out + 'screenshot.png',self.get_image(do_debug=True))
        self.save_markers(folder_out+'markers.txt',do_transform=False)
        self.object.export_mesh(folder_out+'mesh.obj',self.object.coord_vert,self.object.idx_vertex,do_transform=False)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def save_markers(self,filename_out,do_transform = False):
        if do_transform:
            X = self.my_VBO.marker_positions[1:].copy()
            X = numpy.array(X)
            X[:,1] = 0-X[:,1]
            tools_IO.save_mat(X, filename_out,delim=',')
        else:
            tools_IO.save_mat(self.my_VBO.marker_positions[1:], filename_out,delim=',')
        return
# ----------------------------------------------------------------------------------------------------------------------
    def load_markers(self, filename_in, filename_marker_obj,marker_scale=None):

        if marker_scale is not None:
            self.marker_scale = marker_scale

        markers = tools_IO.load_mat(filename_in,dtype=numpy.float,delim=',')
        flag = self.my_VBO.remove_last_object()
        while flag==0:
            flag = self.my_VBO.remove_last_object()

        for marker in markers:
            self.my_VBO.append_object(filename_marker_obj, (0.7, 0.2, 0), do_normalize_model_file=True, svec=(self.marker_scale, self.marker_scale, self.marker_scale), tvec=marker)
        self.bind_VBO()
        return
# ----------------------------------------------------------------------------------------------------------------------
    def start_rotation(self):
        self.on_rotate = True
        self.mat_model_rotation_checkpoint = self.mat_model.copy()
        self.mat_view_rotation_checkpoint = self.eye, self.target, self.up
        return
# ----------------------------------------------------------------------------------------------------------------------
    def stop_rotation(self):
        self.on_rotate = False
        self.mat_model_rotation_checkpoint = None
        self.mat_view_rotation_checkpoint = None
        return
# ----------------------------------------------------------------------------------------------------------------------
    def start_translation(self):
        self.on_translate = True
        self.mat_model_translation_checkpoint = self.mat_model.copy()
        self.mat_view_translation_checkpoint = self.eye, self.target, self.up
        return
# ----------------------------------------------------------------------------------------------------------------------
    def stop_translation(self):
        self.on_translate = False
        self.mat_model_translation_checkpoint = None
        self.mat_view_translation_checkpoint = None
        return
# ----------------------------------------------------------------------------------------------------------------------
    def start_append(self):
        self.on_append = True
        return
# ----------------------------------------------------------------------------------------------------------------------
    def stop_append(self):
        self.on_append = False
        return
# ----------------------------------------------------------------------------------------------------------------------
    def start_remove(self):
        self.on_remove = True
        return
    # ----------------------------------------------------------------------------------------------------------------------
    def stop_remove(self):
        self.on_remove = False
        return
# ----------------------------------------------------------------------------------------------------------------------
    def scale_projection(self,scale):
        aspect_x = 1/self.mat_projection[0,0]
        aspect_y = 1/self.mat_projection[1,1]
        self.__init_mat_projection(aspect_x*scale,aspect_y*scale)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def translate_view_by_scale(self, scale):
        rvec,tvec = tools_pr_geom.decompose_to_rvec_tvec(self.mat_view,do_flip=True)
        tvec*=scale
        self.__init_mat_view_RT(rvec,tvec)

        #E,T,U = tools_pr_geom.mat_view_to_ETU(self.mat_view)
        #F = T-E
        #E*=delta_translate
        #T = E+F
        #self.init_mat_view_ETU(E, T, U)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def translate_view(self, delta_translate):

        if self.on_translate and self.mat_view_translation_checkpoint is not None:
            self.eye,self.target,self.up = self.mat_view_translation_checkpoint

        self.eye+=delta_translate
        self.target+=delta_translate

        self.init_mat_view_ETU(self.eye, self.target, self.up)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def translate_ortho(self, delta_translate):
        factor = 2/self.mat_projection[0,0]
        factor*=delta_translate
        self.__init_mat_projection_ortho(factor)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def scale_model(self, scale_factor):
        self.mat_trns*=scale_factor
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def inverce_transform_model(self,mode):
        I = pyrr.matrix44.create_identity()
        T = pyrr.matrix44.create_from_translation((0,0,0))
        if mode == 'X': I[0, 0] *= -1
        if mode == 'Y': I[1, 1] *= -1
        if mode == 'Z': I[2, 2] *= -1
        M = pyrr.matrix44.multiply(I, T)

        self.mat_trns = pyrr.matrix44.multiply(M, self.mat_trns)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        #self.reset_view(skip_transform=True)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def inverce_screen_Y(self):
        #self.mat_projection[0,0]*=-1
        #glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_projection)
        #self.mat_projection = pyrr.matrix44.create_orthogonal_projection(left, right, bottom, top, near, far)
        #glUniformMatrix4fv(glGetUniformLocation(self.shader, "projection"), 1, GL_FALSE, self.mat_projection)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def transform_model(self,mode):

        T = pyrr.Matrix44.from_scale(self.scale)
        if   mode == 'XY':M = pyrr.matrix44.create_from_z_rotation(-math.pi/2)
        elif mode == 'XZ':M = pyrr.matrix44.create_from_y_rotation(-math.pi/2)
        elif mode == 'YZ':M = pyrr.matrix44.create_from_x_rotation(-math.pi/2)
        elif mode == 'xy':M = pyrr.matrix44.create_from_z_rotation(+math.pi/2)
        elif mode == 'yz':M = pyrr.matrix44.create_from_y_rotation(+math.pi/2)
        elif mode == 'xz':M = pyrr.matrix44.create_from_x_rotation(+math.pi/2)
        self.mat_trns = numpy.dot(T,M)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        self.reset_view(skip_transform=True)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def set_standardize_rvec(self,flag):
        self.is_enabled_standardize_rvec = flag
        return
# ----------------------------------------------------------------------------------------------------------------------
    def standardize_rvec(self,rvec):
        if self.is_enabled_standardize_rvec:
            rvec[0] = min(max(rvec[0],            0.01), math.pi   - 0.01)
            rvec[2] = min(max(rvec[2], -math.pi/2+0.02), math.pi/2 - 0.02)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def rotate_model(self, delta_angle):

        if self.on_rotate and self.mat_model_rotation_checkpoint is not None:
            S, Q, tvec = pyrr.matrix44.decompose(self.mat_model_rotation_checkpoint.copy())
        else:
            S, Q, tvec = pyrr.matrix44.decompose(self.mat_model.copy())

        rvec = tools_pr_geom.quaternion_to_euler(Q)
        rvec+= numpy.array(delta_angle)
        self.standardize_rvec(rvec)

        self.__init_mat_model(rvec,tvec)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def translate_model(self, delta_pos):

        if self.on_translate and self.mat_model_translation_checkpoint is not None:
            rvec, tvec = tools_pr_geom.decompose_to_rvec_tvec(self.mat_model_translation_checkpoint.copy())
        else:
            rvec, tvec = tools_pr_geom.decompose_to_rvec_tvec(self.mat_model.copy())

        tvec += numpy.array(delta_pos)
        self.__init_mat_model(rvec, tvec)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def rotate_view(self, delta_angle):
        if self.on_rotate and self.mat_view_rotation_checkpoint is not None:
            self.eye,self.target,self.up = self.mat_view_rotation_checkpoint


        F = self.target - self.eye
        F = tools_pr_geom.apply_rotation(numpy.array(delta_angle, dtype=float), F)[:3]
        self.up = tools_pr_geom.apply_rotation(numpy.array(delta_angle, dtype=float), self.up)[:3]
        self.target = self.eye + F

        self.init_mat_view_ETU(self.eye, self.target, self.up)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def resize_window(self, W, H):
        self.W = W
        self.H = H
        glViewport(0, 0, W, H)
        self.transform_model('xz')
        return
# ----------------------------------------------------------------------------------------------------------------------
    def reset_view(self,skip_transform=False):

        self.stop_rotation()
        self.stop_append()
        self.stop_remove()
        self.stop_translation()

        self.__init_mat_light(numpy.array((-math.pi / 2, -math.pi / 2, 0)))
        self.__init_mat_projection()
        self.__init_mat_model((0, 0, 0), (0, 0, 0))
        if not skip_transform:
            self.__init_mat_transform(self.scale)

        obj_min = self.object.coord_vert.min()
        obj_max = self.object.coord_vert.max()

        self.init_mat_view_ETU(eye=(0, 0, +5 * (obj_max - obj_min)), target=(0, 0, 0), up=(0, -1, 0))
        #self.__init_mat_view_RT((0,0,0),(0,0,+5 * (obj_max - obj_min)))

        return
# ----------------------------------------------------------------------------------------------------------------------
