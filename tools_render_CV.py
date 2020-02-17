import math
import cv2
import numpy
import pyrr
# ----------------------------------------------------------------------------------------------------------------------
import tools_draw_numpy
numpy.set_printoptions(suppress=True)
numpy.set_printoptions(precision=2)
# ----------------------------------------------------------------------------------------------------------------------
def compose_GL_MAT(rotv,tvecs,do_flip=False):

    rotv = rotv.reshape(3, 1)
    tvecs = tvecs.reshape(3, 1)

    rotMat, jacobian = cv2.Rodrigues(rotv)

    matrix = numpy.identity(4)
    matrix[0:3, 0:3] = rotMat
    matrix[0:3, 3:4] = tvecs
    newMat = numpy.identity(4)
    if do_flip:
        newMat[1][1] = -1
        newMat[2][2] = -1
    matrix = numpy.dot(newMat, matrix)

    return matrix.T
# ----------------------------------------------------------------------------------------------------------------------
def project_points(points_3d, rvec, tvec, camera_matrix, dist):
    #https: // docs.opencv.org / 2.4 / modules / calib3d / doc / camera_calibration_and_3d_reconstruction.html
    R, _ = cv2.Rodrigues(rvec)

    V = numpy.zeros((3,4))
    V[:3,:3] = R
    V[:,3] = numpy.array(tvec).T
    P = numpy.dot(camera_matrix,V)

    points_2d = []

    for each in points_3d:
        point_4d=numpy.array([each[0],each[1],each[2],1])
        x = numpy.dot(P, point_4d)
        points_2d.append(x/x[2])

    points_2d = numpy.array(points_2d)[:,:2].reshape(-1,1,2)

    return points_2d,0
# ----------------------------------------------------------------------------------------------------------------------
def draw_axis(img, camera_matrix, dist, rvec, tvec, axis_length):
    # equivalent to aruco.drawAxis(frame,camera_matrix,dist,rvec, tvec, marker_length)

    axis_3d_end   = numpy.array([[axis_length, 0, 0], [0, axis_length, 0], [0, 0, +axis_length]],dtype = numpy.float32)
    axis_3d_start = numpy.array([[0, 0, 0]],dtype=numpy.float32)

    axis_2d_end, jac = cv2.projectPoints(axis_3d_end, rvec, tvec, camera_matrix, dist)
    axis_2d_start, jac = cv2.projectPoints(axis_3d_start, rvec, tvec, camera_matrix, dist)

    axis_2d_end = axis_2d_end.reshape((3,2))
    axis_2d_start = axis_2d_start.reshape((1,2))

    #axis_2d_end, jac = project_points(axis_3d_end, rvec, tvec, camera_matrix, dist)
    #axis_2d_start, jac = project_points(axis_3d_start, rvec, tvec, camera_matrix, dist)


    img = tools_draw_numpy.draw_line(img, axis_2d_start[0, 1], axis_2d_start[0, 0], axis_2d_end[0, 1],axis_2d_end[0, 0], (0, 0, 255))
    img = tools_draw_numpy.draw_line(img, axis_2d_start[0, 1], axis_2d_start[0, 0], axis_2d_end[1, 1],axis_2d_end[1, 0], (0, 255, 0))
    img = tools_draw_numpy.draw_line(img, axis_2d_start[0, 1], axis_2d_start[0, 0], axis_2d_end[2, 1],axis_2d_end[2, 0], (255, 0, 0))
    return img
# ----------------------------------------------------------------------------------------------------------------------
def draw_cube_numpy(img, camera_matrix, dist, rvec, tvec, scale=(1,1,1),color=(255,128,0),):

    points_3d = numpy.array([[-1, -1, -1], [-1, +1, -1], [+1, +1, -1], [+1, -1, -1],[-1, -1, +1], [-1, +1, +1], [+1, +1, +1], [+1, -1, +1]],dtype = numpy.float32)

    points_3d[:,0]*=scale[0]
    points_3d[:,1]*=scale[1]
    points_3d[:,2]*=scale[2]

    #points_2d, jac = cv2.projectPoints(pooints_3d, rvec, tvec, camera_matrix, dist)
    points_2d, jac = project_points(points_3d, rvec, tvec, camera_matrix, dist)

    points_2d = points_2d.reshape((-1,2))
    for i,j in zip((0,1,2,3,4,5,6,7,0,1,2,3),(1,2,3,0,5,6,7,4,4,5,6,7)):
        img = tools_draw_numpy.draw_line(img, points_2d[i, 1], points_2d[i, 0], points_2d[j, 1],points_2d[j, 0], color)

    return img
# ----------------------------------------------------------------------------------------------------------------------
def draw_cube_numpy_MVP(img,mat_projection, mat_view, mat_model, mat_trns, color=(66, 0, 166)):

    fx, fy = float(img.shape[1]), float(img.shape[0])
    camera_matrix = numpy.array([[fx, 0, fx / 2], [0, fy, fy / 2], [0, 0, 1]])

    points_3d = numpy.array([[-1, -1, -1], [-1, +1, -1], [+1, +1, -1], [+1, -1, -1],[-1, -1, +1], [-1, +1, +1], [+1, +1, +1], [+1, -1, +1]],dtype = numpy.float32)

    points_3d_new = []
    for v in points_3d:
        vv = pyrr.matrix44.apply_to_vector(mat_trns, v)
        vv = pyrr.matrix44.apply_to_vector(mat_model, vv)
        vv = pyrr.matrix44.apply_to_vector(mat_view, vv)
        points_3d_new.append(vv)


    points_2d, jac = project_points(points_3d_new, (0,0,0), (0,0,0), camera_matrix, numpy.zeros(4))
    points_2d = points_2d.reshape((-1,2))
    for i,j in zip((0,1,2,3,4,5,6,7,0,1,2,3),(1,2,3,0,5,6,7,4,4,5,6,7)):
        img = tools_draw_numpy.draw_line(img, points_2d[i, 1], points_2d[i, 0], points_2d[j, 1],points_2d[j, 0], color)

    return img
# ----------------------------------------------------------------------------------------------------------------------
def draw_points_numpy_RT(points_3d, img, camera_matrix, dist, rvec, tvec, scale=(1, 1, 1), color=(66, 0, 166)):

    points_3d[:, 0]*=scale[0]
    points_3d[:, 1]*=scale[1]
    points_3d[:, 2]*=scale[2]

    #points_2d, jac = cv2.projectPoints(points_3d, rvec, tvec, camera_matrix, dist)
    points_2d, jac = project_points(points_3d, rvec, tvec, camera_matrix, dist)

    points_2d = points_2d.reshape((-1,2))
    for point in points_2d:
        img = tools_draw_numpy.draw_circle(img, point[1], point[0], 4, color)

    return img
# ----------------------------------------------------------------------------------------------------------------------
def draw_points_numpy_MVP(points_3d, img, mat_projection, mat_view, mat_model, mat_trns, color=(66, 0, 166),do_debug=False):

    fx, fy = float(img.shape[1]), float(img.shape[0])
    camera_matrix = numpy.array([[fx, 0, fx / 2], [0, fy, fy / 2], [0, 0, 1]])

    points_3d_new = []
    for v in points_3d:
        vv = pyrr.matrix44.apply_to_vector(mat_trns ,v)
        vv = pyrr.matrix44.apply_to_vector(mat_model,vv)
        vv = pyrr.matrix44.apply_to_vector(mat_view ,vv)
        points_3d_new.append(vv)

    #points_2d, jac = cv2.projectPoints(points_3d_new, (0,0,0), (0,0,0), camera_matrix, numpy.zeros(4))
    points_2d, jac = project_points(points_3d_new, (0,0,0), (0,0,0), camera_matrix, numpy.zeros(4))

    points_2d = points_2d.reshape((-1,2))
    points_2d[:,0]=img.shape[1]-points_2d[:,0]
    for point in points_2d:
        img = tools_draw_numpy.draw_circle(img, int(point[1]), int(point[0]), 4, color)


    if do_debug:
        for p2,p3 in zip(points_2d,points_3d):
            print(p3,p2)
        print()
    return img
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
def get_ray(point_2d, img, mat_projection, mat_view, mat_model, mat_trns):

    fx, fy = float(img.shape[1]), float(img.shape[0])
    camera_matrix = numpy.array([[fx, 0, fx / 2], [0, fy, fy / 2], [0, 0, 1]])

    Z1 = -1
    X1 = (point_2d[0]*Z1 - Z1*fx/2)/fx
    Y1 = (point_2d[1]*Z1 - Z1*fy/2)/fy
    ray_begin = numpy.array((X1, Y1, Z1))

    Z2 = +1
    X2 = (point_2d[0]*Z2 - Z2*fx/2)/fx
    Y2 = (point_2d[1]*Z2 - Z2*fy/2)/fy
    ray_end = numpy.array((X2, Y2, Z2))

    #check
    points_2d_check, jac = project_points(numpy.array([(X1, Y1, Z1),(X2,Y2,Z2)]), (0, 0, 0), (0, 0, 0), camera_matrix, numpy.zeros(4))

    i_mat_view  = pyrr.matrix44.inverse(mat_view)
    i_mat_model = pyrr.matrix44.inverse(mat_model)
    i_mat_trans = pyrr.matrix44.inverse(mat_trns)

    #i_mat_view  = mat_view.T
    #i_mat_model = mat_model.T
    #i_mat_trans = mat_trns.T

    ray_begin_v = pyrr.matrix44.apply_to_vector(i_mat_view , ray_begin)
    ray_begin_check_v = pyrr.matrix44.apply_to_vector(mat_view, ray_begin_v)

    ray_begin_m = pyrr.matrix44.apply_to_vector(i_mat_model, ray_begin_v)
    ray_begin_check_m = pyrr.matrix44.apply_to_vector(mat_model, ray_begin_m)

    ray_begin_t = pyrr.matrix44.apply_to_vector(i_mat_trans , ray_begin_m)
    ray_begin_check_t = pyrr.matrix44.apply_to_vector(mat_trns, ray_begin_t)

    #check
    vv = pyrr.matrix44.apply_to_vector(mat_trns, ray_begin_t)
    vv = pyrr.matrix44.apply_to_vector(mat_model, vv)
    vv = pyrr.matrix44.apply_to_vector(mat_view, vv)
    x = (vv == ray_begin)


    ray_end = pyrr.matrix44.apply_to_vector(i_mat_view , ray_end)
    ray_end = pyrr.matrix44.apply_to_vector(i_mat_model, ray_end)
    ray_end = pyrr.matrix44.apply_to_vector(i_mat_trans, ray_end)




    return ray_begin_t,ray_end
# ----------------------------------------------------------------------------------------------------------------------
def line_plane_intersection(planeNormal, planePoint, rayDirection, rayPoint, epsilon=1e-6):
    ndotu = numpy.array(planeNormal[:3]).dot(numpy.array(rayDirection[:3]))
    if numpy.isnan(ndotu) or abs(ndotu) < epsilon :
        return None

    w = numpy.array(rayPoint[:3]) - numpy.array(planePoint[:3])
    si = -numpy.array(planeNormal[:3]).dot(w) / ndotu
    Psi = w + si * numpy.array(rayDirection[:3]) + numpy.array(planePoint[:3])
    return Psi
# ----------------------------------------------------------------------------------------------------------------------
def normalize(x):
    n = numpy.sqrt((x ** 2).sum())
    if n>0:
        y = x/n
    else:
        y = x
    return y
# ----------------------------------------------------------------------------------------------------------------------
def get_normal(triangles_3d):
    A = triangles_3d[1] - triangles_3d[0]
    B = triangles_3d[2] - triangles_3d[0]
    Nx = A[1] * B[2] - A[2] * B[1]
    Ny = A[2] * B[0] - A[0] * B[2]
    Nz = A[0] * B[1] - A[1] * B[0]
    n = -numpy.array((Nx, Ny, Nz), dtype=numpy.float)
    n = normalize(n)
    return n
# ----------------------------------------------------------------------------------------------------------------------
def get_interception_ray_triangle(pos, direction, triangle):
    n = get_normal(triangle)
    collision = line_plane_intersection(n, triangle[0,:3], direction[:3], pos[:3], epsilon=1e-6)

    if collision is not None:
        if is_point_inside_triangle(collision,triangle):
            return collision

    return None
# ----------------------------------------------------------------------------------------------------------------------
def get_interception_ray_triangles(pos, direction, coord_vert, coord_norm, idxv, idxn):
    collisions = []

    for iv,inr in zip(idxv,idxn):
        triangle = coord_vert[iv]
        n = coord_norm[inr[0]]#n0 = get_normal(triangle)

        collision = line_plane_intersection(n, triangle[0,:3], direction[:3], pos[:3], epsilon=1e-6)

        if collision is not None:
            if is_point_inside_triangle(collision,triangle):
                collisions.append(collision)

    if len(collisions)==0:return None
    if len(collisions)==1:return collisions[0]

    X = numpy.array([collision-pos for collision in collisions])
    X = numpy.mean(X**2,axis=1)
    i = numpy.argmin(X)
    return collisions[i]
# ----------------------------------------------------------------------------------------------------------------------
def is_point_inside_triangle(contact_point, P):

    V1=P[0]
    V2=P[1]
    V3=P[2]

    line1 = normalize(V1-contact_point)
    line2 = normalize(V2-contact_point)
    dot1=numpy.dot(line1,line2)

    line1 = normalize(V2-contact_point)
    line2 = normalize(V3-contact_point)
    dot2=numpy.dot(line1,line2)

    line1 = normalize(V3-contact_point)
    line2 = normalize(V1-contact_point)
    dot3=numpy.dot(line1,line2)

    if numpy.isnan(dot1) or numpy.isnan(dot2) or numpy.isnan(dot3):
        return  False

    dot1 = min(+1,max(dot1,-1))
    dot2 = min(+1,max(dot2,-1))
    dot3 = min(+1,max(dot3,-1))

    accumilator = math.acos(dot1) + math.acos (dot2) + math.acos(dot3)
    if accumilator < (2*math.pi - 0.01):
        return False

    return True
# ----------------------------------------------------------------------------------------------------------------------