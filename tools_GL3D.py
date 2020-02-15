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
import tools_image
import tools_aruco
import tools_wavefront
import tools_calibrate
# ----------------------------------------------------------------------------------------------------------------------
numpy.set_printoptions(suppress=True)
numpy.set_printoptions(precision=2)
# ----------------------------------------------------------------------------------------------------------------------
class render_GL3D(object):

    def __init__(self,filename_obj,W=640, H=480,is_visible=True,do_normalize=True,scale=(1,1,1)):

        #glutInit()
        #glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glfw.init()
        self.scale = scale
        self.do_normalize = do_normalize
        self.bg_color  = numpy.array([76, 76, 76,1])/255

        self.W,self.H  = W,H
        glfw.window_hint(glfw.VISIBLE, is_visible)
        self.window = glfw.create_window(self.W, self.H, "GL viewer", None, None)
        glfw.make_context_current(self.window)

        self.init_objects(filename_obj, numpy.array([192, 128, 0])/255.0,do_normalize=self.do_normalize)
        self.__init_shader()

        self.VBO = None
        self.__init_VBO()
        self.reset_view()

        return
# ----------------------------------------------------------------------------------------------------------------------
    def init_objects(self, filename_obj, mat_color,do_normalize):
        self.mat_list = [mat_color]
        self.obj_list = [tools_wavefront.ObjLoader()]
        self.obj_list[0].load_model(filename_obj,mat_color,do_normalize)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def append_object(self,filename_obj,mat_color):
        self.mat_list.append(mat_color)
        self.obj_list.append(tools_wavefront.ObjLoader())
        self.obj_list[-1].load_model(filename_obj,mat_color)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_shader(self):
        vert_shader = """#version 330
                                    in layout(location = 0) vec3 position;
                                    in layout(location = 1) vec3 color;
                                    in layout(location = 2) vec3 vertNormal;
                                    uniform mat4 transform,view,model,projection,light;
                                    out vec3 inColor;
                                    out vec3 fragNormal;
                                    void main()
                                    {
                                        fragNormal = (light * vec4(vertNormal, 0.0f)).xyz;
                                        gl_Position = projection * view * model * transform * vec4(position, 1.0f);
                                        inColor = color;
                                    }"""

        frag_shader = """#version 330
                                    in vec3 inColor;
                                    in vec3 fragNormal;
                                    out vec4 outColor;
                                    void main()
                                    {
                                        //vec3 ambientLightIntensity  = inColor;
                                        vec3 ambientLightIntensity  = vec3(0.1f, 0.1f, 0.1f);
                                        vec3 sunLightIntensity      = vec3(1.0f, 1.0f, 1.0f);
                                        vec3 sunLightDirection      = normalize(vec3(+0.0f, -1.0f, +0.0f));



                                        vec3 lightIntensity = ambientLightIntensity + sunLightIntensity * max(dot(fragNormal, sunLightDirection), 0.0f);
                                        outColor = vec4(inColor*lightIntensity, 1);
                                    }"""



        self.shader = OpenGL.GL.shaders.compileProgram(OpenGL.GL.shaders.compileShader(vert_shader, GL_VERTEX_SHADER),
                                                       OpenGL.GL.shaders.compileShader(frag_shader, GL_FRAGMENT_SHADER))
        glUseProgram(self.shader)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_VBO(self):

        obj = self.obj_list[-1]


        self.VBO = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.VBO)
        glBufferData(GL_ARRAY_BUFFER, obj.model.itemsize * len(obj.model), obj.model, GL_STATIC_DRAW)

        # positions
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, obj.model.itemsize * 3, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # colors
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, obj.model.itemsize * 3, ctypes.c_void_p(obj.color_offset))
        glEnableVertexAttribArray(1)

        # normals
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, obj.model.itemsize * 3, ctypes.c_void_p(obj.normal_offset))
        glEnableVertexAttribArray(2)

        glClearColor(self.bg_color[0], self.bg_color[1], self.bg_color[2], self.bg_color[3])
        glEnable(GL_DEPTH_TEST)

        # glEnable(GL_LIGHTING)
        # glEnable(GL_LIGHT0)
        # glShadeModel(GL_SMOOTH)
        # glShadeModel(GL_FLAT)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_projection(self):

        fx, fy = float(self.W), float(self.H)
        left, right, bottom, top = -0.5, (self.W - fx / 2) / fx, (fy / 2 - self.H) / fy, 0.5
        near, far = 1, 1000

        self.mat_camera = numpy.array([[fx, 0, fx / 2], [0, fy, fy / 2], [0, 0, 1]])
        self.mat_projection = pyrr.matrix44.create_perspective_projection_from_bounds(left,right,bottom,top,near,far)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "projection"), 1, GL_FALSE, self.mat_projection)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_view_RT(self, rvec,tvec,flip=True):
        #R = pyrr.matrix44.create_from_eulers(rvec)
        #T = pyrr.matrix44.create_from_translation(tvec)
        #self.mat_view = pyrr.matrix44.multiply(R, T)
        self.mat_view = tools_aruco.compose_GL_MAT(numpy.array(rvec, dtype=numpy.float),numpy.array(tvec, dtype=numpy.float),flip)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "view"), 1, GL_FALSE, self.mat_view)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_view_ETU(self, eye, target, up):
        self.mat_view = pyrr.matrix44.create_look_at(eye, target, up)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "view"), 1, GL_FALSE, self.mat_view)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_model(self,rvec, tvec):
        self.mat_model = pyrr.matrix44.create_from_eulers(rvec)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "model"), 1, GL_FALSE, self.mat_model)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_transform(self,scale_vec):

        self.mat_trns = pyrr.Matrix44.from_scale(scale_vec)
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __init_mat_light(self,r_vec):
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "light")    , 1, GL_FALSE, pyrr.matrix44.create_from_eulers(r_vec))
        return
# ----------------------------------------------------------------------------------------------------------------------

    #projection * view * model * transform
    # model maps from an object's local coordinate space into world space,
    # view from world space to camera space,
    # projection from camera to screen.
# ----------------------------------------------------------------------------------------------------------------------
    def draw(self,rvec=None,tvec=None,flip=True):
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        if rvec is not None and tvec is not None:
            self.__init_mat_view_RT(rvec,tvec,flip)
        glDrawArrays(GL_TRIANGLES, 0, self.obj_list[0].n_vertex)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def get_image(self, rvec=None, tvec=None, flip=True, do_debug=False):
        self.draw(rvec, tvec,flip)
        image_buffer = glReadPixels(0, 0, self.W, self.H, OpenGL.GL.GL_RGB, OpenGL.GL.GL_UNSIGNED_BYTE)
        image = numpy.frombuffer(image_buffer, dtype=numpy.uint8).reshape(self.H, self.W, 3)
        image = cv2.flip(image, 0)
        if do_debug:
            self.draw_mat(self.mat_projection, 20, 20, image)
            self.draw_mat(self.mat_view, 20, 120, image)
            self.draw_mat(self.mat_model, 20, 220, image)
            self.draw_mat(self.mat_camera, 20, 350, image)
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
    def start_rotation(self):
        self.on_rotate = True
        self.mat_model_checkpoint = self.mat_model
        return
    # ----------------------------------------------------------------------------------------------------------------------
    def stop_rotation(self):
        self.on_rotate = False
        self.mat_model_checkpoint = None
        return
# ----------------------------------------------------------------------------------------------------------------------
    def translate_view(self, delta_translate):
        eye, target, up = tools_calibrate.calculate_eye_target_up(self.mat_view)
        eye *= delta_translate
        self.__init_mat_view_ETU(eye, target, up)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def scale_model(self, scale_factor):
        self.mat_trns*=scale_factor
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def transform_model(self,mode):

        M = pyrr.matrix44.create_identity()
        if   mode == 'XY':M = pyrr.matrix44.create_from_z_rotation(-math.pi/2)
        elif mode == 'XZ':M = pyrr.matrix44.create_from_y_rotation(-math.pi/2)
        elif mode == 'YZ':M = pyrr.matrix44.create_from_x_rotation(-math.pi/2)
        elif mode == 'xy':M = pyrr.matrix44.create_from_z_rotation(+math.pi/2)
        elif mode == 'yz':M = pyrr.matrix44.create_from_y_rotation(+math.pi/2)
        elif mode == 'xz':M = pyrr.matrix44.create_from_x_rotation(+math.pi/2)
        self.mat_trns = M * self.mat_trns.max()
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "transform"), 1, GL_FALSE, self.mat_trns)
        self.reset_view(skip_transform=True)

        #print(self.mat_trns)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def __align_light(self, euler_model):
        vec_light = self.vec_initial_light + euler_model - self.vec_initial_model
        self.__init_mat_light(vec_light)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def __display_info(self):

        S, Q, tvec = pyrr.matrix44.decompose(self.mat_model)
        rvec = tools_calibrate.quaternion_to_euler(Q)
        print('rvec', rvec * 180 / math.pi)
        return
# ----------------------------------------------------------------------------------------------------------------------
    def rotate_model(self, delta_angle):

        if self.on_rotate and self.mat_model_checkpoint is not None:
            S, Q, tvec = pyrr.matrix44.decompose(self.mat_model_checkpoint)
        else:
            S, Q, tvec = pyrr.matrix44.decompose(self.mat_model)

        rvec  = tools_calibrate.quaternion_to_euler(Q) + numpy.array(delta_angle)
        rvec[0] = numpy.clip(rvec[0],0.01,math.pi-0.01)
        self.__init_mat_model(rvec,tvec)
        #self.__align_light(rvec)

        return
# ----------------------------------------------------------------------------------------------------------------------
    def reset_view(self,skip_transform=False):

        if self.do_normalize:
            obj = self.obj_list[0]

            obj_min = numpy.array(obj.coord_vert).astype(numpy.float).min()
            obj_max = numpy.array(obj.coord_vert).astype(numpy.float).max()
            self.vec_initial_light = (0,math.pi/2,-math.pi/2)
            self.vec_initial_model = (math.pi/2,math.pi/2,0)
            self.__init_mat_view_ETU(eye=(0, 0, -5 * (obj_max - obj_min)), target=(0, 0, 0), up=(0, -1, 0))
            self.__init_mat_model(self.vec_initial_model,(0,0,0))
            if not skip_transform:
                self.__init_mat_transform((1,1,1))
            self.__init_mat_light(self.vec_initial_light)
            self.__init_mat_projection()
            self.stop_rotation()
        else:
            self.__init_mat_model((0,0,0), (0, 0, 0))
            self.vec_initial_light = (0, math.pi / 2, -math.pi / 2)
            self.__init_mat_light(self.vec_initial_light)
            self.__init_mat_projection()
            self.__init_mat_transform(self.scale)
            self.stop_rotation()
        return
# ----------------------------------------------------------------------------------------------------------------------
    def resize_window(self,W,H):
        self.W = W
        self.H = H
        glViewport(0, 0, W, H)
        self.transform_model('xz')
        return
# ----------------------------------------------------------------------------------------------------------------------
