import math
import cv2
import pyrr
import numpy
from sklearn.neighbors import NearestNeighbors
from scipy.linalg import polar
# ----------------------------------------------------------------------------------------------------------------------
def best_fit_transform(A, B):
    '''
    Calculates the least-squares best-fit transform that maps corresponding points A to B in m spatial dimensions
    Input:
      A: Nxm numpy array of corresponding points
      B: Nxm numpy array of corresponding points
    Returns:
      T: (m+1)x(m+1) homogeneous transformation matrix that maps A on to B
      R: mxm rotation matrix
      t: mx1 translation vector
    '''

    assert A.shape == B.shape

    # get number of dimensions
    m = A.shape[1]

    # translate points to their centroids
    centroid_A = numpy.mean(A, axis=0)
    centroid_B = numpy.mean(B, axis=0)
    AA = A - centroid_A
    BB = B - centroid_B

    # rotation matrix
    H = numpy.dot(AA.T, BB)
    U, S, Vt = numpy.linalg.svd(H)
    R = numpy.dot(Vt.T, U.T)

    # special reflection case
    if numpy.linalg.det(R) < 0:
       Vt[m-1,:] *= -1
       R = numpy.dot(Vt.T, U.T)

    # translation
    t = centroid_B.T - numpy.dot(R, centroid_A.T)

    # homogeneous transformation
    T = numpy.identity(m + 1)
    T[:m, :m] = R
    T[:m, m] = t

    return T, R, t
# ---------------------------------------------------------------------------------------------------------------------
def nearest_neighbor(src, dst):

    assert src.shape == dst.shape
    neigh = NearestNeighbors(n_neighbors=1)
    neigh.fit(dst)
    distances, indices = neigh.kneighbors(src, return_distance=True)
    return distances.ravel(), indices.ravel()
# ---------------------------------------------------------------------------------------------------------------------
def icp(A, B, init_pose=None, max_iterations=200, tolerance=0.001):
    '''
    The Iterative Closest Point method: finds best-fit transform that maps points A on to points B
    Input:
        A: Nxm numpy array of source mD points
        B: Nxm numpy array of destination mD point
        init_pose: (m+1)x(m+1) homogeneous transformation
        max_iterations: exit algorithm after max_iterations
        tolerance: convergence criteria
    Output:
        T: final homogeneous transformation that maps A on to B
        distances: Euclidean distances (errors) of the nearest neighbor
        i: number of iterations to converge
    '''

    assert A.shape == B.shape

    # get number of dimensions
    m = A.shape[1]

    # make points homogeneous, copy them to maintain the originals
    src = numpy.ones((m + 1, A.shape[0]))
    dst = numpy.ones((m + 1, B.shape[0]))
    src[:m,:] = numpy.copy(A.T)
    dst[:m,:] = numpy.copy(B.T)

    # apply the initial pose estimation
    if init_pose is not None:
        src = numpy.dot(init_pose, src)

    prev_error = 0

    for i in range(max_iterations):
        # find the nearest neighbors between the current source and destination points
        distances, indices = nearest_neighbor(src[:m,:].T, dst[:m,:].T)

        # compute the transformation between the current source and nearest destination points
        T,_,_ = best_fit_transform(src[:m,:].T, dst[:m,indices].T)

        # update the current source
        src = numpy.dot(T, src)

        # check error
        mean_error = numpy.mean(distances)
        if numpy.abs(prev_error - mean_error) < tolerance:
            break
        prev_error = mean_error
        print(numpy.mean(distances))

    # calculate final transformation
    T,_,_ = best_fit_transform(A, src[:m,:].T)

    return T, distances, i
# ---------------------------------------------------------------------------------------------------------------------
def fit_homography(X_source,X_target):
    method = cv2.RANSAC
    #method = cv2.LMEDS
    #method = cv2.RHO
    H, mask = cv2.findHomography(X_source, X_target, method, 3.0)

    result  = cv2.perspectiveTransform(X_source.reshape(-1, 1, 2),H).reshape((-1,2))

    loss =  ((result-X_target)**2).mean()

    return H, result
# ----------------------------------------------------------------------------------------------------------------------
def fit_affine(X_source,X_target):
    A, _ = cv2.estimateAffine2D(numpy.array(X_source), numpy.array(X_target), confidence=0.95)
    result = cv2.transform(X_source.reshape(-1, 1, 2), A).reshape((-1,2))
    loss = ((result - X_target) ** 2).mean()
    return A, result
# ----------------------------------------------------------------------------------------------------------------------
def fit_euclid(X_source,X_target):
    E, _ = cv2.estimateAffinePartial2D(numpy.array(X_source), numpy.array(X_target))
    result = cv2.transform(X_source.reshape(-1, 1, 2), E).reshape((-1,2))

    #M=numpy.eye(4,dtype=numpy.float)
    #M[:2,:2]=E[:,:2]
    #M[:2, 3]=E[:,2]

    #X4D = numpy.full((X_source.shape[0],4),1,dtype=numpy.float)
    #X4D[:,:2]=X_source
    #result2 = pyrr.matrix44.multiply(M,X4D.T).T

    loss = ((result - X_target) ** 2).mean()

    return E, result
# ----------------------------------------------------------------------------------------------------------------------
def fit_translation(X_source,X_target):
    t = numpy.mean((X_target  - X_source ),axis=0)
    E = pyrr.matrix44.create_from_translation(t).T
    #X4D = numpy.full((X_source.shape[0],4),1,dtype=numpy.float)
    #X4D[:,:2]=X_source
    result = pyrr.matrix44.multiply(E,X_source.T).T
    loss = ((result - X_target) ** 2).mean()
    return E, result
# ----------------------------------------------------------------------------------------------------------------------
def fit_custom(X_source,X_target):



    return
# ----------------------------------------------------------------------------------------------------------------------
def compose_projection_mat(fx, fy, scale_factor):
    P = numpy.array([[fx, 0, 0, fx / 2], [0, fy, 0, fy / 2], [0, 0, 1, 0], [0, 0, 0, 1]])
    P[:, 3] *= scale_factor[0]
    P /= scale_factor[0]

    #P = numpy.array([[fx/scale_factor[0], 0, 0, fx / 2], [0, fy/scale_factor[1], 0, fy / 2], [0, 0, 1, 0], [0, 0, 0, 1]])

    return P
# ----------------------------------------------------------------------------------------------------------------------
def decompose_into_TRK(M):
    tvec = M[:3, 3]
    L = M.copy()
    L[:3, 3] = 0
    R, K = polar(L)
    R = numpy.array(R)
    #f, X = numpy.linalg.eig(K)

    if numpy.linalg.det(R) < 0:
        R[:3, :3] = -R[:3, :3]
        K[:3, :3] = -K[:3, :3]

    rvec = rotationMatrixToEulerAngles(R[:3,:3])
    T = pyrr.matrix44.create_from_translation(tvec).T
    R = pyrr.matrix44.create_from_eulers(rvec).T

    M_check = pyrr.matrix44.multiply(T,pyrr.matrix44.multiply(R,K))

    return T,R,K
# ----------------------------------------------------------------------------------------------------------------------
def decompose_model_view(M):
    S, Q, tvec_view = pyrr.matrix44.decompose(M)
    rvec_model = quaternion_to_euler(Q)
    mat_model = pyrr.matrix44.create_from_eulers(rvec_model)
    mat_view = pyrr.matrix44.create_from_translation(tvec_view)
    R = pyrr.matrix44.create_from_eulers((0,math.pi,math.pi))
    mat_view = pyrr.matrix44.multiply(mat_view, R)
    return mat_model, mat_view
# ----------------------------------------------------------------------------------------------------------------------
def decompose_model_view_to_RRTT(mat_model, mat_view):
    S, Q, tvec_model = pyrr.matrix44.decompose(mat_model)
    rvec_model = quaternion_to_euler(Q)
    S, Q, tvec_view = pyrr.matrix44.decompose(mat_view)
    rvec_view = quaternion_to_euler(Q)
    return rvec_model,tvec_model,rvec_view,tvec_view
# ----------------------------------------------------------------------------------------------------------------------
def rotationMatrixToEulerAngles(R,do_flip=False):

    Rt = numpy.transpose(R)
    shouldBeIdentity = numpy.dot(Rt, R)
    I = numpy.identity(3, dtype=R.dtype)
    n = numpy.linalg.norm(I - shouldBeIdentity)

    if True or (n < 1e-6):

        sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])

        singular = sy < 1e-6

        if not singular:
            x = math.atan2(R[2, 1], R[2, 2])
            y = math.atan2(-R[2, 0], sy)
            z = math.atan2(R[1, 0], R[0, 0])
        else:
            x = math.atan2(-R[1, 2], R[1, 1])
            y = math.atan2(-R[2, 0], sy)
            z = 0

        if do_flip:
            x*=-1
            y*=-1

    return numpy.array([x, z, y])
#----------------------------------------------------------------------------------------------------------------------
def quaternion_to_euler(Q):
    x, y, z, w = Q[0],Q[1],Q[2],Q[3]

    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    X = math.degrees(math.atan2(t0, t1))

    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    Y = math.degrees(math.asin(t2))

    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    Z = math.degrees(math.atan2(t3, t4))

    return numpy.array((X, Z, Y))*math.pi/180
#----------------------------------------------------------------------------------------------------------------------
def euler_to_quaternion(rvec):
    yaw, pitch, roll = rvec[0],rvec[1], rvec[2]
    qx = numpy.sin(roll / 2) * numpy.cos(pitch / 2) * numpy.cos(yaw / 2) - numpy.cos(roll / 2) * numpy.sin(pitch / 2) * numpy.sin(yaw / 2)
    qy = numpy.cos(roll / 2) * numpy.sin(pitch / 2) * numpy.cos(yaw / 2) + numpy.sin(roll / 2) * numpy.cos(pitch / 2) * numpy.sin(yaw / 2)
    qz = numpy.cos(roll / 2) * numpy.cos(pitch / 2) * numpy.sin(yaw / 2) - numpy.sin(roll / 2) * numpy.sin(pitch / 2) * numpy.cos(yaw / 2)
    qw = numpy.cos(roll / 2) * numpy.cos(pitch / 2) * numpy.cos(yaw / 2) + numpy.sin(roll / 2) * numpy.sin(pitch / 2) * numpy.sin(yaw / 2)
    return numpy.array((qx, qy, qz, qw))
#----------------------------------------------------------------------------------------------------------------------
def eulerAnglesToRotationMatrix(theta):

    R_x = numpy.array([[1, 0, 0],
                    [0, math.cos(theta[0]), -math.sin(theta[0])],
                    [0, math.sin(theta[0]), math.cos(theta[0])]
                    ])

    R_y = numpy.array([[math.cos(theta[1]), 0, math.sin(theta[1])],
                    [0, 1, 0],
                    [-math.sin(theta[1]), 0, math.cos(theta[1])]
                    ])

    R_z = numpy.array([[math.cos(theta[2]), -math.sin(theta[2]), 0],
                    [math.sin(theta[2]), math.cos(theta[2]), 0],
                    [0, 0, 1]
                    ])

    R = numpy.dot(R_z, numpy.dot(R_y, R_x))

    return R
# ----------------------------------------------------------------------------------------------------------------------
def project_points(points_3d, rvec, tvec, camera_matrix, dist):
    #https: // docs.opencv.org / 2.4 / modules / calib3d / doc / camera_calibration_and_3d_reconstruction.html

    #R, _ = cv2.Rodrigues(rvec)
    R = pyrr.matrix44.create_from_eulers(rvec)

    M=numpy.zeros((4,4))
    M[:3,:3] = R[:3,:3]
    M[:3,3] = numpy.array(tvec).T

    P = numpy.zeros((3,4))
    P[:3,:3] = camera_matrix

    points_2d = []

    for each in points_3d:
        X = pyrr.matrix44.apply_to_vector(M, numpy.array([each[0],each[1],each[2],1]))
        uv = numpy.dot(P, X)
        points_2d.append(uv/uv[2])


    points_2d = numpy.array(points_2d)[:,:2].reshape(-1,1,2)

    return points_2d,0
# ----------------------------------------------------------------------------------------------------------------------
def project_points_ortho(points_3d, rvec, tvec, dist,fx,fy,scale_factor):

    R = pyrr.matrix44.create_from_eulers(rvec).T
    T = pyrr.matrix44.create_from_translation(tvec).T
    RT = pyrr.matrix44.multiply(T, R)
    P = compose_projection_mat(fx,fy,scale_factor)

    PRTS = pyrr.matrix44.multiply(P,RT)
    X4D = numpy.full((points_3d.shape[0],4),1,dtype=numpy.float)
    X4D[:,:3]=points_3d
    points_2d = pyrr.matrix44.multiply(PRTS,X4D.T).T
    points_2d = numpy.array(points_2d)[:, :2].reshape(-1, 1, 2)

    return points_2d ,0
# ----------------------------------------------------------------------------------------------------------------------
def project_points_ortho_modelview(points_3d, modelview, dist,fx,fy,scale_factor):

    P = compose_projection_mat(fx, fy, scale_factor)

    PRT = pyrr.matrix44.multiply(P,modelview)
    X4D = numpy.full((points_3d.shape[0],4),1,dtype=numpy.float)
    X4D[:,:3]=points_3d
    points_2d = pyrr.matrix44.multiply(PRT,X4D.T).T

    points_2d = numpy.array(points_2d)[:, :2].reshape(-1, 1, 2)

    return points_2d ,0
# ----------------------------------------------------------------------------------------------------------------------
def my_solve_PnP(L3D, L2D, K, dist):
    #return cv2.solvePnP(L3D, L2D, K, dist)

    fx = K[0,0]
    fy = K[1,1]
    cx = K[0,2]
    cy = K[1,2]
    n = L3D.shape[0]


    #Step 1. Construct matrix A, whose size is 2n x12.
    A = numpy.zeros((2 * n, 12))
    for i in range(n):
        pt3d = L3D[i]
        pt2d = L2D[i]

        x = pt3d[0]
        y = pt3d[1]
        z = pt3d[2]
        u = pt2d[0]
        v = pt2d[1]

        A[2 * i, 0] = x * fx
        A[2 * i, 1] = y * fx
        A[2 * i, 2] = z * fx
        A[2 * i, 3] = fx
        A[2 * i, 4] = 0.0
        A[2 * i, 5] = 0.0
        A[2 * i, 6] = 0.0
        A[2 * i, 7] = 0.0
        A[2 * i, 8] = x * cx - u * x
        A[2 * i, 9] = y * cx - u * y
        A[2 * i, 10] = z * cx - u * z
        A[2 * i, 11] = cx - u
        A[2 * i + 1, 0] = 0.0
        A[2 * i + 1, 1] = 0.0
        A[2 * i + 1, 2] = 0.0
        A[2 * i + 1, 3] = 0.0
        A[2 * i + 1, 4] = x * fy
        A[2 * i + 1, 5] = y * fy
        A[2 * i + 1, 6] = z * fy
        A[2 * i + 1, 7] = fy
        A[2 * i + 1, 8] = x * cy - v * x
        A[2 * i + 1, 9] = y * cy - v * y
        A[2 * i + 1, 10] = z * cy - v * z
        A[2 * i + 1, 11] = cy - v

    #Step 2. Solve Ax = 0 by SVD
    u, s, vh = numpy.linalg.svd(A)

    a1 = vh[0, 11]
    a2 = vh[1, 11]
    a3 = vh[2, 11]
    a4 = vh[3, 11]
    a5 = vh[4, 11]
    a6 = vh[5, 11]
    a7 = vh[6, 11]
    a8 = vh[7, 11]
    a9 = vh[8, 11]
    a10= vh[9, 11]
    a11= vh[10,11]
    a12= vh[11,11]

    R_bar = numpy.array([[a1, a2, a3], [a5, a6, a7], [a9, a10, a11]])
    U_R, V_Sigma , V_R = numpy.linalg.svd(R_bar)
    R = numpy.dot(U_R , V_R.T)


    beta = 1.0 / ((V_Sigma[0] + V_Sigma[1] + V_Sigma[2]) / 3.0)

    t_bar = numpy.array((a4, a8, a12))
    t = beta * t_bar

    R = pyrr.matrix44.create_from_matrix33(R)

    S, Q, tvec_view = pyrr.matrix44.decompose(R)
    rvec = quaternion_to_euler(Q)


    return (0, rvec, t)
# ----------------------------------------------------------------------------------------------------------------------